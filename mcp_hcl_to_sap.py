from mcp.server.fastmcp import FastMCP
import javalang
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open("D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    logger.error("config.json not found")
    raise

# MCP Server Setup
#mcp = fastmcp.MCPServer()
mcp = FastMCP("code-converter")

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
    # Check direct implementation
    if node.implements and any(i.name == "ControllerCommand" for i in node.implements):
        return True
    # Check if extends ControllerCommandImpl
    if node.extends and node.extends.name == "ControllerCommandImpl":
        return True
    return False

# Helper function to generate Spring controller code
def generate_spring_controller(class_name: str, methods: list, properties: list):
    controller_code = [
        "import org.springframework.web.bind.annotation.RestController;",
        "import org.springframework.web.bind.annotation.PostMapping;",
        "import org.springframework.web.bind.annotation.RequestBody;",
        "import com.example.ResponseDTO;",
        f"@RestController",
        f"public class {class_name}Controller {{",
        f"    private final {class_name}Service {class_name.lower()}Service;",
        f"    public {class_name}Controller({class_name}Service {class_name.lower()}Service) {{",
        f"        this.{class_name.lower()}Service = {class_name.lower()}Service;",
        "    }"
    ]
    for method in methods:
        if method.name == "performExecute":
            controller_code.append(f'    @PostMapping("/api/{class_name.lower()}")')
            controller_code.append(f'    public ResponseDTO execute(@RequestBody {class_name}DTO request) {{')
            controller_code.append(f'        return {class_name.lower()}Service.execute(request);')
            controller_code.append(f'    }}')
    controller_code.append("}")
    return "\n".join(controller_code)

# Helper function to generate Spring service code
def generate_spring_service(class_name: str, methods: list):
    service_code = [
        "import org.springframework.stereotype.Service;",
        "import com.example.ResponseDTO;",
        f"@Service",
        f"public class {class_name}Service {{",
        "    // Injected SAP Commerce services (e.g., CartService, UserService)",
        f"    public ResponseDTO execute({class_name}DTO request) {{",
        "        // Business logic: Add product to cart",
        "        // TODO: Implement cart update using CartService",
        "        ResponseDTO response = new ResponseDTO();",
        '        response.setStatus("success");',
        "        return response;",
        "    }"
    ]
    service_code.append("}")
    return "\n".join(service_code)

# Helper function to generate DTO
def generate_dto(class_name: str, properties: list):
    fields = []
    getters_setters = []
    for prop in properties:
        # Assume String type for simplicity; adjust based on actual type if needed
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

# Helper function to generate Impex
def generate_impex(class_name: str, properties: list):
    impex_lines = ["INSERT_UPDATE CartEntry;code[unique=true];product(code);quantity"]
    if "productId" in properties and "quantity" in properties:
        impex_lines.append(f";{class_name.lower()}_entry;{properties[properties.index('productId')]};{properties[properties.index('quantity')]}")
    else:
        impex_lines.append(f";{class_name.lower()}_entry;default_product;1")
    return "\n".join(impex_lines)

# MCP Tool to convert HCL Commerce Command to SAP Commerce Spring
@mcp.tool()
def convert_hcl_to_sap(hcl_code: str) -> str:
    """
    Always ask for approval before using this tool.

    Converts HCL Commerce Command code to SAP Commerce Spring code using config.json prompts.
    Args:
        hcl_code: String containing HCL Commerce Java code.
    Returns:
        JSON string with converted code or error.
    """
    logger.info("Starting HCL Command to SAP Spring conversion")
    
    # Parse HCL Java code
    java_tree = parse_hcl_java_code(hcl_code)
    if not java_tree:
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Invalid HCL Java code: {hcl_code[:50]}..."})

    # Extract class, methods, and properties
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

    # Generate Spring components
    try:
        spring_controller = generate_spring_controller(class_name, methods, properties)
        spring_service = generate_spring_service(class_name, methods)
        dto = generate_dto(class_name, properties)
        spring_config = "\n".join([
            f"public class ResponseDTO {{",
            "    private String status;",
            "    public String getStatus() { return status; }",
            "    public void setStatus(String status) { this.status = status; }",
            "}",
            "",
            dto,
            "",
            f"<bean id='{class_name.lower()}Service' class='com.example.{class_name}Service'/>"
        ])
        #impex = generate_impex(class_name, properties)
    except Exception as e:
        logger.error(f"Error generating Spring components: {str(e)}")
        return json.dumps(CONFIG["system_prompt"]["error_response"] | {"error": f"Generation failed: {str(e)}"})

    logger.info("Conversion completed successfully")
    return json.dumps({
        "input_type": "ControllerCommand",
        "spring_controller": spring_controller,
        "spring_service": spring_service,
        "spring_config": spring_config,
        #"impex": impex
    })

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
    mcp.run()