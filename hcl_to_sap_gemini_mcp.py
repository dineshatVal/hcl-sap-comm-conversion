import os
from google.generativeai import GenerativeModel
from mcp.server.fastmcp import FastMCP
import google.generativeai as genai
from dotenv import load_dotenv
import json
import datetime

load_dotenv() # Load environment variables from .env file

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
#model = GenerativeModel('gemini-1.5-flash') # Or 'gemini-1.5-pro' for more complex tasks
model = GenerativeModel('gemini-2.5-pro')

#INPUT_HCL_CODE_DIR = 'input'
INPUT_HCL_CODE_DIR = "D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\input" # Change this to your actual input directory
INPUT_FLOW_DESCRIPTIONS_DIR = "D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\input\\flow_descriptions"
INPUT_SAP_EXAMPLES_DIR = "D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\input\\sap_commerce_examples"
#OUTPUT_SAP_CODE_DIR = 'output'
OUTPUT_SAP_CODE_DIR = "D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\output" # Change this to your actual input directory
OUTPUT_CONVERSION_LOGS_DIR = "D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\output\\logs"

PROMPT_FILE_PATH = 'D:\\python-samples\\hcl-sap-poc\\framework-conv-poc\\prompts\\sap_commerce_conversion_prompt.txt'


# Ensure output directories exist
os.makedirs(OUTPUT_SAP_CODE_DIR, exist_ok=True)
os.makedirs(OUTPUT_CONVERSION_LOGS_DIR, exist_ok=True)

mcp = FastMCP("code-converter-files-gemini")

def read_file_content(filepath):
    """Reads the content of a given file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

def write_file_content(filepath, content):
    """Writes content to a given file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote to {filepath}")
    except Exception as e:
        print(f"Error writing to file {filepath}: {e}")

def load_prompt_template(filepath):
    """Loads the prompt template from a file."""
    template = read_file_content(filepath)
    if template is None:
        raise FileNotFoundError(f"Prompt template file not found or empty: {filepath}")
    return template

# Load the prompt template once when the script starts
try:
    GLOBAL_PROMPT_TEMPLATE = load_prompt_template(PROMPT_FILE_PATH)
except FileNotFoundError as e:
    print(f"Critical error: {e}")
    exit(1)

def generate_conversion_prompt(hcl_code_content, flow_description, sap_examples=None, filename=""):
    """
    Constructs the prompt for Gemini Code Assist.
    This is the MOST CRITICAL part and needs careful engineering.
    """
    prompt = f"""
    You are an expert in HCL Commerce and SAP Commerce (Hybris) development.
    Your task is to convert HCL Commerce code for a specific feature into SAP Commerce compliant code,
    following SAP Commerce framework best practices (e.g., extensions, services, DAOs, controllers, items.xml).

    **Context:**
    I am providing you with HCL Commerce code for a feature and a text description of its functional flow.
    Your goal is to understand the HCL code's purpose within this flow and then re-implement it using SAP Commerce principles.

    **HCL Commerce Code (from file: {filename}):**
    ```hcl
    {hcl_code_content}
    ```

    **Feature Flow Description:**
    ```text
    {flow_description}
    ```
    """

    if sap_examples:
        prompt += f"""
        **SAP Commerce Framework Examples/Best Practices (for reference):**
        (These examples demonstrate how SAP Commerce components are typically structured. Please adhere to these patterns.)
        ```sap_commerce_examples
        {sap_examples}
        ```
        """

    prompt += """
    **Conversion Instructions:**
    1.  **Analyze the HCL Code:** Understand its functionality, dependencies, and business logic within the context of the provided flow description.
    2.  **Identify SAP Commerce Equivalents:** Determine how the HCL functionality maps to SAP Commerce concepts (e.g., servlets to controllers, custom tables to items.xml, custom logic to services/DAOs).
    3.  **Generate SAP Commerce Code:**
        * Create new files as needed (e.g., `MyFeatureService.java`, `MyFeatureDAO.java`, `MyFeatureController.java`, `myfeature-items.xml`, Spring configuration XMLs).
        * Ensure the generated code adheres strictly to SAP Commerce's framework, naming conventions, and best practices.
        * Use the provided SAP Commerce examples as a guide for structure and coding style.
        * Do not just translate syntax; re-architect if necessary to fit the SAP Commerce paradigm.
        * Add comments to explain the conversion logic and any assumptions made.
        * If a direct conversion is not feasible or requires significant re-design, indicate that and suggest a high-level approach.
    4.  **Output Format:** Provide the converted SAP Commerce code for each generated file, clearly separated, with the suggested filename for each.

    **Example Output Format (start your response like this, generating all relevant files):**

    --- FILE: path/to/my/extension/src/myextension/core/service/impl/DefaultMyFeatureService.java ---
    ```java
    // SAP Commerce compliant Java code for DefaultMyFeatureService
    // ...
    ```

    --- FILE: path/to/my/extension/src/myextension/core/dao/impl/DefaultMyFeatureDAO.java ---
    ```java
    // SAP Commerce compliant Java code for DefaultMyFeatureDAO
    // ...
    ```

    --- FILE: path/to/my/extension/web/src/myextension/controller/MyFeatureController.java ---
    ```java
    // SAP Commerce compliant Java code for MyFeatureController
    // ...
    ```

    --- FILE: path/to/my/extension/resources/myextension-items.xml ---
    ```xml
    ```

    --- FILE: path/to/my/extension/resources/myextension-spring.xml ---
    ```xml
    ```
    """
    return prompt.strip()

def generate_conversion_prompt_openai(hcl_code_content, flow_description, sap_examples=None, filename=""):
    """
    Constructs the prompt for OpenAI models using a loaded template.
    """
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z%z")

    # The prompt now uses f-string like placeholders for dynamic content
    # The template itself should contain placeholders like {hcl_code_content}, {flow_description}, etc.
    # Note: sap_examples section needs conditional formatting, so it's a bit trickier with pure f-strings in a file.
    # We'll use .format() and handle the optional part separately.

    base_prompt = GLOBAL_PROMPT_TEMPLATE

    # Handle the optional sap_examples section
    if sap_examples:
        # If the template has a dedicated {sap_examples} placeholder, populate it directly
        # Otherwise, you might need to insert it more dynamically
        # For our current prompt, it's already structured to accept it directly
        sap_examples_section = f"""
        **SAP Commerce Framework Examples/Best Practices (for reference):**
        (These examples demonstrate how SAP Commerce components are typically structured. Please adhere to these patterns.
        They might include sample `items.xml`, service/DAO/controller implementations, or Spring configurations.)
        ```sap_commerce_examples
        {sap_examples}
        ```
        """
    else:
        # Remove the placeholder or the entire block if no examples are provided
        # This requires the template to have a clear way to identify the examples block.
        # A simple way for this prompt structure is to replace it with an empty string
        # if the template has the {sap_examples} placeholder.
        sap_examples_section = ""
        # If your template explicitly includes the examples section even when empty,
        # you might need to carefully remove it using regex or string manipulation
        # if you don't want the heading to appear without content.
        # For simplicity, if {sap_examples} is just a placeholder, passing an empty string
        # will work if the template is well-designed.


    # Use .format() to fill in the variables
    # Ensure all placeholders in your .txt file are covered here.
    formatted_prompt = base_prompt.format(
        current_datetime=current_datetime,
        hcl_code_content=hcl_code_content,
        flow_description=flow_description,
        filename=filename,
        sap_examples=sap_examples_section.strip() # Pass the formatted section or empty string
    )

    return formatted_prompt.strip()

def process_hcl_feature(hcl_code_filepaths, flow_filepath, sap_examples_dir=None):
    """
    Processes an HCL Commerce feature for conversion.
    """
    all_hcl_code = ""
    for fp in hcl_code_filepaths:
        content = read_file_content(fp)
        if content:
            all_hcl_code += f"\n--- Start of file: {os.path.basename(fp)} ---\n"
            all_hcl_code += content
            all_hcl_code += f"\n--- End of file: {os.path.basename(fp)} ---\n"

    flow_description = read_file_content(flow_filepath)
    if not all_hcl_code or not flow_description:
        print(f"Skipping feature due to missing code or flow description: {flow_filepath}")
        return

    sap_examples_content = None
    if sap_examples_dir and os.path.exists(sap_examples_dir):
        sap_examples_content = ""
        for root, _, files in os.walk(sap_examples_dir):
            for file in files:
                filepath = os.path.join(root, file)
                content = read_file_content(filepath)
                if content:
                    sap_examples_content += f"\n--- Start of SAP Example: {os.path.basename(filepath)} ---\n"
                    sap_examples_content += content
                    sap_examples_content += f"\n--- End of SAP Example: {os.path.basename(filepath)} ---\n"

    # Use the name of the flow file (without extension) as a feature identifier for logs
    feature_name = os.path.splitext(os.path.basename(flow_filepath))[0]
    log_filepath = os.path.join(OUTPUT_CONVERSION_LOGS_DIR, f"{feature_name}_conversion_log.txt")

    print(f"Generating prompt for feature: {feature_name}")
    #prompt = generate_conversion_prompt(all_hcl_code, flow_description, sap_examples_content, filename=os.path.basename(hcl_code_filepaths[0] if hcl_code_filepaths else "N/A")) # Using first HCL file name for context
    prompt = generate_conversion_prompt_openai(all_hcl_code, flow_description, sap_examples_content, filename=os.path.basename(hcl_code_filepaths[0] if hcl_code_filepaths else "N/A"))

    try:
        # Send to Gemini Code Assist
        print("Sending request to Gemini Code Assist...")
        response = model.generate_content(prompt)
        converted_code_text = response.text
        print("Received response from Gemini Code Assist.")

        # Log the full response for review
        write_file_content(log_filepath, f"Prompt:\n{prompt}\n\n--- Gemini Response ---\n{converted_code_text}")

        # Parse the output and write to files
        # This parsing needs to be robust as LLM output format can vary.
        # A simple delimiter based parsing is shown here.
        output_files = converted_code_text.split('--- FILE: ')[1:] # Split by delimiter
        for file_section in output_files:
            try:
                # Extract path and content
                lines = file_section.split('\n', 1)
                if len(lines) < 2:
                    print(f"Skipping malformed output section: {file_section[:50]}...")
                    continue

                relative_path = lines[0].strip()
                code_content = lines[1].strip()

                if relative_path.startswith('---'):
                    relative_path = relative_path.lstrip('-').strip()
                if relative_path.endswith('---'):
                    relative_path = relative_path.rstrip('-').strip()

                # Remove markdown code block fences if present
                if code_content.startswith("```") and code_content.endswith("```"):
                    code_content = code_content.lstrip("`").lstrip(code_content.split('\n')[0]).rstrip("`").strip()

                # Remove trailing '---' delimiter if present
                code_lines = code_content.splitlines()
                while code_lines and code_lines[-1].strip() == '---':
                    code_lines = code_lines[:-1]
                code_content = '\n'.join(code_lines)

                # Construct full output path
                output_filepath = os.path.join(OUTPUT_SAP_CODE_DIR, relative_path)
                os.makedirs(os.path.dirname(output_filepath), exist_ok=True) # Ensure subdirectories exist
                write_file_content(output_filepath, code_content)
            except Exception as e:
                print(f"Error parsing and writing individual file section: {e}\nSection:\n{file_section[:200]}...")

    except Exception as e:
        print(f"Error communicating with Gemini Code Assist or processing response for feature {feature_name}: {e}")
        write_file_content(log_filepath, f"Error: {e}\nPrompt:\n{prompt}")

# MCP Tool to convert HCL Commerce Command to SAP Commerce Spring (stdio)
@mcp.tool()
def convert_hcl_sap() -> str:

    """
    Converts all HCL Commerce Java files in the input directory
    to SAP Commerce framework files, saving outputs to the output directory, using Gemini Code Assist.
    
    """

    # Automatically process all .java files in the input directory
    java_files = [f for f in os.listdir(INPUT_HCL_CODE_DIR) if f.endswith('.java')]
    if not java_files:
        print("No Java files found in input directory.")
        return
    
    java_files_updated = [os.path.join(INPUT_HCL_CODE_DIR, f) for f in os.listdir(INPUT_HCL_CODE_DIR) if f.endswith('.java')]

    # Use a generic/default flow description if available, else empty string
    default_flow_path = os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt')
    #if os.path.exists(default_flow_path):
    #    flow_description_path = default_flow_path
    #else:
    #    flow_description_path = None

    #for java_file in java_files:
    #    hcl_code_path = [os.path.join(INPUT_HCL_CODE_DIR, java_file)]
    #    print(f"\n--- Processing file: {java_file} ---")
        #process_hcl_feature(hcl_code_path, flow_description_path, None)
    process_hcl_feature(java_files_updated, default_flow_path, None)

    print("\nCode conversion process completed. Please review the output folder for generated code and logs.")
    print("Manual review, testing, and potential refactoring of the generated SAP Commerce code are essential.")
    return json.dumps({
        "status": "success",
        "message": "HCL to SAP conversion completed successfully."
    })

if __name__ == "__main__":
    convert_hcl_sap()
    #mcp.run()