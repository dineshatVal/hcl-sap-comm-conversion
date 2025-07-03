import os
from google.generativeai import GenerativeModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = GenerativeModel('gemini-1.5-flash') # Or 'gemini-1.5-pro' for more complex tasks

INPUT_HCL_CODE_DIR = 'input'
INPUT_FLOW_DESCRIPTIONS_DIR = 'input/flow_descriptions'
INPUT_SAP_EXAMPLES_DIR = 'input/sap_commerce_examples' # Optional
OUTPUT_SAP_CODE_DIR = 'output'
OUTPUT_CONVERSION_LOGS_DIR = 'output/logs'

# Ensure output directories exist
os.makedirs(OUTPUT_SAP_CODE_DIR, exist_ok=True)
os.makedirs(OUTPUT_CONVERSION_LOGS_DIR, exist_ok=True)

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
    prompt = generate_conversion_prompt(all_hcl_code, flow_description, sap_examples_content, filename=os.path.basename(hcl_code_filepaths[0] if hcl_code_filepaths else "N/A")) # Using first HCL file name for context

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

                # Construct full output path
                output_filepath = os.path.join(OUTPUT_SAP_CODE_DIR, relative_path)
                os.makedirs(os.path.dirname(output_filepath), exist_ok=True) # Ensure subdirectories exist
                write_file_content(output_filepath, code_content)
            except Exception as e:
                print(f"Error parsing and writing individual file section: {e}\nSection:\n{file_section[:200]}...")

    except Exception as e:
        print(f"Error communicating with Gemini Code Assist or processing response for feature {feature_name}: {e}")
        write_file_content(log_filepath, f"Error: {e}\nPrompt:\n{prompt}")


def main():
    # Map HCL code files to their respective flow descriptions
    # This is a manual mapping step based on your understanding of the features.
    # Example:
    features_to_process = {
        "invoice_display_feature": {
            "hcl_code": [
                os.path.join(INPUT_HCL_CODE_DIR, 'views-ext.xml'),
                os.path.join(INPUT_HCL_CODE_DIR, 'LINPayInvoiceResults.jsp'),
                os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmd.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmdImpl.java'),
                os.path.join(INPUT_HCL_CODE_DIR,'GetInvoicesDTO.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBean.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBeanHandler.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'isplayInvoicesDataBean.xml')
                # Add all relevant HCL code files for this feature
            ],
            "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt'),
            #"sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'login_examples') # Optional
            
        },
       # "product_display_feature": {
       #     "hcl_code": [
       #         os.path.join(INPUT_HCL_CODE_DIR, 'ProductDisplayCmd.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'ProductView.jsp'),
       #     ],
       #     "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'product_display_flow.txt'),
       #     "sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'product_examples') # Optional
       # }
        # Add more features as needed
    }

    for feature_name, details in features_to_process.items():
        print(f"\n--- Processing Feature: {feature_name} ---")
        process_hcl_feature(details["hcl_code"], details["flow_description"], details.get("sap_examples"))

    print("\nCode conversion process completed. Please review the output_folder for generated code and logs.")
    print("Manual review, testing, and potential refactoring of the generated SAP Commerce code are essential.")

if __name__ == "__main__":
    main()