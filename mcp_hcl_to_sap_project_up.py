from pathlib import Path
from mcp.server.fastmcp import FastMCP
import javalang
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open("D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\config-folder.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    logger.error("config-folder.json not found")
    raise

# MCP Server Setup
#mcp = fastmcp.MCPServer()
mcp = FastMCP("code-converter-files-up")

# Helper function to parse HCL Commerce Java code
def parse_hcl_java_code(code: str):
    try:
        tree = javalang.parse.parse(code)
        return tree
    except javalang.parser.JavaSyntaxError as e:
        logger.error(f"Error parsing Java code: {str(e)} at {e.location}")
        return None

# Helper function to check if a class is a ControllerCommand
def is_controller_command(node):
    if node.implements and any(i.name == "ControllerCommand" for i in node.implements):
        return True
    if node.extends and node.extends.name == "ControllerCommandImpl":
        return True
    return False

# Helper function to traverse AST recursively
def traverse_ast(node, visitor_func):
    if not node:
        return
    visitor_func(node)
    try:
        children = getattr(node, "children", [])
    except AttributeError:
        logger.debug(f"Node {type(node).__name__} has no children attribute, skipping")
        return
    for child in children:
        if isinstance(child, (list, tuple)):
            for item in child:
                if item and not isinstance(item, (set, str, bool, int, float)):
                    traverse_ast(item, visitor_func)
        elif child and not isinstance(child, (set, str, bool, int, float)):
            traverse_ast(child, visitor_func)

# Helper function to check if facade is needed
def needs_facade(methods: list, properties: list):
    logger.info("Checking if facade is needed")
    has_if_statement = [False]
    put_calls = [0]
    has_command_context = [False]

    def visitor(node):
        if isinstance(node, javalang.tree.IfStatement):
            logger.info("Found IfStatement")
            has_if_statement[0] = True
        if isinstance(node, javalang.tree.MethodInvocation) and node.member == "put" and getattr(node, "qualifier", None) == "resp":
            put_calls[0] += 1
            logger.info(f"Found TypedProperty.put call, total: {put_calls[0]}")
        if isinstance(node, javalang.tree.MethodInvocation) and getattr(node, "qualifier", None) == "commandContext":
            logger.info("Found CommandContext usage")
            has_command_context[0] = True

    for method in methods:
        if method.name == "performExecute":
            traverse_ast(method, visitor)
    
    return has_if_statement[0] or put_calls[0] > 1 or has_command_context[0]

# Helper function to generate Spring controller code
def generate_spring_controller(class_name: str, methods: list, properties: list, use_facade: bool):
    controller_code = [
        "import org.springframework.web.bind.annotation.RestController;",
        "import org.springframework.web.bind.annotation.PostMapping;",
        "import org.springframework.web.bind.annotation.RequestBody;",
        "import com.example.ResponseDTO;",
        f"@RestController",
        f"public class {class_name}Controller {{",
        f"    private final {class_name}{'Facade' if use_facade else 'Service'} {class_name.lower()}{'Facade' if use_facade else 'Service'};",
        f"    public {class_name}Controller({class_name}{'Facade' if use_facade else 'Service'} {class_name.lower()}{'Facade' if use_facade else 'Service'}) {{",
        f"        this.{class_name.lower()}{'Facade' if use_facade else 'Service'} = {class_name.lower()}{'Facade' if use_facade else 'Service'};",
        "    }"
    ]
    for method in methods:
        if method.name == "performExecute":
            controller_code.append(f'    @PostMapping("/api/{class_name.lower()}")')
            controller_code.append(f'    public ResponseDTO execute(@RequestBody {class_name}DTO request) {{')
            controller_code.append(f'        return {class_name.lower()}{"Facade" if use_facade else "Service"}.execute(request);')
            controller_code.append(f'    }}')
    controller_code.append("}")
    return "\n".join(controller_code)

# Helper function to generate Spring facade code
def generate_spring_facade(class_name: str, methods: list, properties: list):
    facade_code = [
        "import org.springframework.stereotype.Component;",
        "import com.example.ResponseDTO;",
        "import de.hybris.platform.core.model.order.OrderModel;",
        "import de.hybris.platform.order.OrderService;",
        "import de.hybris.platform.servicelayer.model.ModelService;",
        f"@Component",
        f"public class {class_name}Facade {{",
        f"    private final {class_name}Service {class_name.lower()}Service;",
        "    private final OrderService orderService;",
        "    private final ModelService modelService;",
        "",
        f"    public {class_name}Facade({class_name}Service {class_name.lower()}Service, OrderService orderService, ModelService modelService) {{",
        f"        this.{class_name.lower()}Service = {class_name.lower()}Service;",
        "        this.orderService = orderService;",
        "        this.modelService = modelService;",
        "    }",
        f"    public ResponseDTO execute({class_name}DTO request) {{",
        "        ResponseDTO response = new ResponseDTO();",
        "        try {",
        f"            if (request.getOrderId() != null && request.getUserId() != null && request.getPaymentMethod() != null) {{",
        f"                OrderModel order = orderService.getOrderForCode(request.getOrderId());",
        '                if ("CREDIT_CARD".equals(request.getPaymentMethod()) && "PENDING".equals(order.getStatus().getCode())) {',
        '                    response.setStatus("success");',
        '                    response.setOrderId(request.getOrderId());',
        '                    response.setMessage("Order processed successfully");',
        "                    // Add storeId from configuration or service if needed",
        "                } else {",
        '                    response.setStatus("failure");',
        '                    response.setError("Invalid payment method or order status");',
        "                }",
        "            } else {",
        '                response.setStatus("failure");',
        '                response.setError("Missing required fields");',
        "            }",
        "        } catch (Exception e) {",
        '            response.setStatus("failure");',
        '            response.setError("Error processing order: " + e.getMessage());',
        "        }",
        "        return response;",
        "    }"
    ]
    facade_code.append("}")
    return "\n".join(facade_code)

# Helper function to generate Spring service code
def generate_spring_service(class_name: str, methods: list):
    service_code = [
        "import org.springframework.stereotype.Service;",
        "import com.example.ResponseDTO;",
        "import de.hybris.platform.core.model.order.OrderModel;",
        "import de.hybris.platform.order.OrderService;",
        f"@Service",
        f"public class {class_name}Service {{",
        "    private final OrderService orderService;",
        "",
        f"    public {class_name}Service(OrderService orderService) {{",
        "        this.orderService = orderService;",
        "    }",
        f"    public ResponseDTO execute({class_name}DTO request) {{",
        "        ResponseDTO response = new ResponseDTO();",
        "        // Delegate to SAP Commerce OrderService for persistence",
        "        try {",
        f"            OrderModel order = orderService.getOrderForCode(request.getOrderId());",
        '            response.setStatus("success");',
        "        } catch (Exception e) {",
        '            response.setStatus("failure");',
        '            response.setError("Service error: " + e.getMessage());',
        "        }",
        "        return response;",
        "    }}"
    ]
    service_code.append("}")
    return "\n".join(service_code)

# Helper function to generate DTO
def generate_dto(class_name: str, properties: list):
    fields = []
    getters_setters = []
    for prop in properties:
        fields.append(f"    private String {prop};")
        getters_setters.extend([
            f"    public String get{prop[0].upper() + prop[1:]}() {{ return {prop}; }}",
            f"    public void set{prop[0].upper() + prop[1:]}(String {prop}) {{ this.{prop} = {prop}; }}"
        ])
    return "\n".join([
        f"public class {class_name}DTO {{",
        *fields,
        "",
        *getters_setters,
        "}"
    ])

# Helper function to generate ResponseDTO
def generate_response_dto():
    return "\n".join([
        "public class ResponseDTO {",
        "    private String status;",
        "    private String orderId;",
        "    private String message;",
        "    private String error;",
        "    public String getStatus() { return status; }",
        "    public void setStatus(String status) { this.status = status; }",
        "    public String getOrderId() { return orderId; }",
        "    public void setOrderId(String orderId) { this.orderId = orderId; }",
        "    public String getMessage() { return message; }",
        "    public void setMessage(String message) { this.message = message; }",
        "    public String getError() { return error; }",
        "    public void setError(String error) { this.error = error; }",
        "}"
    ])

# Helper function to generate Impex
def generate_impex(class_name: str, properties: list):
    if "orderId" in properties:
        return "\n".join([
            "INSERT_UPDATE Order;code[unique=true];user(uid);paymentType(code)",
            f";{class_name.lower()}_{properties[properties.index('orderId')]};{properties[properties.index('userId') if 'userId' in properties else 'userId']};{properties[properties.index('paymentMethod') if 'paymentMethod' in properties else 'paymentMethod']}"
        ])
    return "\n".join(["INSERT_UPDATE Order;code[unique=true];user(uid);paymentType(code)", f";{class_name.lower()}_default;default;default"])

# Helper function to save output files
def save_output_files(class_name: str, output_data: dict, output_dir: str):
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_dir_path / f"{class_name}Controller.java", "w") as f:
            f.write(output_data["spring_controller"])
        if output_data.get("spring_facade"):
            with open(output_dir_path / f"{class_name}Facade.java", "w") as f:
                f.write(output_data["spring_facade"])
        with open(output_dir_path / f"{class_name}Service.java", "w") as f:
            f.write(output_data["spring_service"])
        with open(output_dir_path / f"{class_name}Config.java", "w") as f:
            f.write(output_data["spring_config"])
        #with open(output_dir_path / f"{class_name}.impex", "w") as f:
        #    f.write(output_data["impex"])
        logger.info(f"Saved output files for {class_name} in {output_dir}")
    except Exception as e:
        logger.error(f"Error saving output files for {class_name}: {str(e)}")
        raise

# MCP Tool to convert HCL Commerce Command to SAP Commerce Spring (stdio)
@mcp.tool()
def convert_hcl_to_sap(hcl_code: str) -> str:
    """
    Converts HCL Commerce Command code provided as a string to SAP Commerce Spring code.
    Args:
        hcl_code: String containing HCL Commerce Java code.
    Returns:
        JSON string with converted code or error.
    """
    logger.info("Starting HCL Command to SAP Spring conversion (stdio)")
    
    java_tree = parse_hcl_java_code(hcl_code)
    if not java_tree:
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Invalid HCL Java code: {hcl_code[:50]}..."})

    class_name = None
    methods = []
    properties = []
    is_controller = False
    for path, node in java_tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            class_name = node.name
            is_controller = is_controller_command(node)
        elif isinstance(node, javalang.tree.MethodDeclaration):
            methods.append(node)
        elif isinstance(node, javalang.tree.FieldDeclaration):
            for declarator in node.declarators:
                properties.append(declarator.name)

    if not class_name:
        return json.dumps(
            CONFIG["system_prompt"]["error_response"] | {"error": "No class found in HCL code"}
        )
    if not is_controller:
        return json.dumps(
            CONFIG["system_prompt"]["error_response"] | {"error": f"Class {class_name} does not extend ControllerCommandImpl or implement ControllerCommand"}
        )

    try:
        use_facade = needs_facade(methods, properties)
        spring_controller = generate_spring_controller(class_name, methods, properties, use_facade)
        spring_facade = generate_spring_facade(class_name, methods, properties) if use_facade else ""
        spring_service = generate_spring_service(class_name, methods)
        dto = generate_dto(class_name, properties)
        spring_config = "\n".join([
            generate_response_dto(),
            "",
            dto,
            "",
            f"<bean id='{class_name.lower()}Service' class='com.example.{class_name}Service'/>",
            f"<bean id='{class_name.lower()}Facade' class='com.example.{class_name}Facade'/>" if use_facade else ""
        ])
        impex = generate_impex(class_name, properties)
    except Exception as e:
        logger.error(f"Error generating Spring components: {str(e)}")
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Generation failed: {str(e)}"})

    logger.info("Conversion completed successfully (stdio)")
    return json.dumps({
        "input_type": "ControllerCommand",
        "spring_controller": spring_controller,
        "spring_facade": spring_facade,
        "spring_service": spring_service,
        "spring_config": spring_config,
        "impex": impex
    })

# MCP Tool to convert HCL Commerce files to SAP Commerce files
@mcp.tool()
def convert_hcl_to_sap_files() -> str:
    """
    Converts all HCL Commerce Java files in the input directory specified in config.json
    to SAP Commerce Spring files, saving outputs to the output directory.
    Returns:
        JSON string with a summary of processed files and any errors.
    """
    logger.info("Starting HCL Command to SAP Spring conversion (file-based)")
    logger.info(f"Current working directory: {os.getcwd()}")
    input_dir = CONFIG.get("input_dir", str(Path(__file__).parent / "input"))
    output_dir = CONFIG.get("output_dir", str(Path(__file__).parent / "output"))
    
    input_path = Path(input_dir)
    logger.info(f"Resolved input directory: {input_path.resolve()}")
    logger.info(f"Input directory exists: {input_path.exists()}, is directory: {input_path.is_dir()}")
    if not input_path.exists():
        logger.error(f"Input directory {input_dir} does not exist")
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Input directory {input_dir} does not exist"})
    if not input_path.is_dir():
        logger.error(f"Input path {input_dir} is not a directory")
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Input path {input_dir} is not a directory"})

    java_files = list(input_path.glob("*.[jJ][aA][vV][aA]"))
    logger.info(f"Found {len(java_files)} Java files: {[str(f) for f in java_files]}")
    if not java_files:
        logger.warning(f"No Java files found in {input_dir}")
        return json.dumps({"results": [], "warning": f"No Java files found in {input_dir}"})

    results = []
    for file_path in java_files:
        logger.info(f"Processing file: {file_path}")
        try:
            with open(file_path, "r") as f:
                hcl_code = f.read()
            
            java_tree = parse_hcl_java_code(hcl_code)
            if not java_tree:
                results.append({"file": str(file_path), "error": "Invalid Java code"})
                continue

            class_name = None
            methods = []
            properties = []
            is_controller = False
            for path, node in java_tree:
                if isinstance(node, javalang.tree.ClassDeclaration):
                    class_name = node.name
                    is_controller = is_controller_command(node)
                elif isinstance(node, javalang.tree.MethodDeclaration):
                    methods.append(node)
                elif isinstance(node, javalang.tree.FieldDeclaration):
                    for declarator in node.declarators:
                        properties.append(declarator.name)

            if not class_name:
                results.append({"file": str(file_path), "error": "No class found in HCL code"})
                continue
            if not is_controller:
                results.append({"file": str(file_path), "error": f"Class {class_name} does not extend ControllerCommandImpl or implement ControllerCommand"})
                continue

            try:
                use_facade = needs_facade(methods, properties)
                output_data = {
                    "input_type": "ControllerCommand",
                    "spring_controller": generate_spring_controller(class_name, methods, properties, use_facade),
                    "spring_facade": generate_spring_facade(class_name, methods, properties) if use_facade else "",
                    "spring_service": generate_spring_service(class_name, methods),
                    "spring_config": "\n".join([
                        generate_response_dto(),
                        "",
                        generate_dto(class_name, properties),
                        "",
                        f"<bean id='{class_name.lower()}Service' class='com.example.{class_name}Service'/>",
                        f"<bean id='{class_name.lower()}Facade' class='com.example.{class_name}Facade'/>" if use_facade else ""
                    ]),
                    #"impex": generate_impex(class_name, properties)
                }
                save_output_files(class_name, output_data, output_dir)
                results.append({"file": str(file_path), "status": "success", "class_name": class_name})
            except Exception as e:
                logger.error(f"Error generating Spring components for {file_path}: {str(e)}")
                results.append({"file": str(file_path), "error": f"Conversion failed: {str(e)}"})
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            results.append({"file": str(file_path), "error": f"File processing failed: {str(e)}"})

    logger.info("File-based conversion completed")
    return json.dumps({"results": results})

# MCP Resource to provide system prompt
@mcp.resource("prompt://system")
def get_system_prompt():
    """
    Returns the system prompt from config.json.
    """
    return json.dumps(CONFIG["system_prompt"])

# Start the MCP Server
if __name__ == "__main__":
    logger.info("Starting MCP server for HCL to SAP conversion")
    #mcp.run()
    result = convert_hcl_to_sap_files()
    print(result)