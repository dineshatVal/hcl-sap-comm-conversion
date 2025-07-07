import datetime
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
#model = GenerativeModel('gemini-1.5-flash') # Or 'gemini-1.5-pro' for more complex tasks
model = GenerativeModel('gemini-2.5-pro')

INPUT_HCL_CODE_DIR = 'input'
INPUT_FLOW_DESCRIPTIONS_DIR = 'input/flow_descriptions'
INPUT_SAP_EXAMPLES_DIR = 'input/sap_commerce_examples' # Optional
OUTPUT_SAP_CODE_DIR = 'output'
OUTPUT_CONVERSION_LOGS_DIR = 'output/logs'

PROMPT_FILE_PATH = 'prompts/sap_commerce_conversion_prompt.txt' # Define the path to your prompt file


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

def process_hcl_feature(hcl_code_filepaths, flow_filepath, sap_examples_dir):
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
       # "invoice_display_feature": {
       #     "hcl_code": [
       #         os.path.join(INPUT_HCL_CODE_DIR, 'views-ext.xml'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'LINPayInvoiceResults.jsp'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmd.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesTaskCmdImpl.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'GetInvoicesDTO.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBean.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'DisplayInvoicesDataBeanHandler.java'),
       #         os.path.join(INPUT_HCL_CODE_DIR, 'isplayInvoicesDataBean.xml')
                # Add all relevant HCL code files for this feature
       #     ],
       #     "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt'),
            #"sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'examples') # Optional
            
        #},
        "account_balance_feature": {
            "hcl_code": [
                os.path.join(INPUT_HCL_CODE_DIR, 'views-ext.xml'),
                os.path.join(INPUT_HCL_CODE_DIR, 'LINGetAccountBalance.jsp'),
                os.path.join(INPUT_HCL_CODE_DIR, 'LINMyAccountSelfServicesHandler.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsTaskCmdImpl.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsTaskCmd.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsCmdImpl.java'),
                os.path.join(INPUT_HCL_CODE_DIR, 'AccountBalanceAndStatementsCmd.java')
                # Add all relevant HCL code files for this feature
            ],
            "flow_description": os.path.join(INPUT_FLOW_DESCRIPTIONS_DIR, 'RequestFlow.txt'),
            #"sap_examples": os.path.join(INPUT_SAP_EXAMPLES_DIR, 'examples') # Optional
            
        },
        # Add more features as needed
    }

    for feature_name, details in features_to_process.items():
        print(f"\n--- Processing Feature: {feature_name} ---")
        process_hcl_feature(details["hcl_code"], details["flow_description"], details.get("sap_examples"))

    print("\nCode conversion process completed. Please review the output_folder for generated code and logs.")
    print("Manual review, testing, and potential refactoring of the generated SAP Commerce code are essential.")

if __name__ == "__main__":
    main()