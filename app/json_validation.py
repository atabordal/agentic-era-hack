import json
import io
import os
import sys
from vertexai.generative_models import GenerativeModel
import google.auth
from google.api_core.client_options import ClientOptions


class JSONValidator:
    def __init__(self, pdf_content, project_id="qwiklabs-gcp-00-5fdb2d368561", location="eu"):
        self.project_id = project_id
        self.location = location
        self.agente_verificador = None
        self.agente_corregidor = None
        self.json_data = "[{}]"
        self.pdf_text = ""
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize the Vertex AI agents."""
        self.agente_verificador = VertexAI(
            model="gemini-2.0-flash-thinking-exp-01-21",
            system_instruction=PROMPT_VERIFICAR,
            temperature=0.2,
        )

        self.agente_corregidor = VertexAI(
            model="gemini-2.0-pro-exp-02-05",
            system_instruction=PROMPT_CORREGIR,
            temperature=0.1,
        )

    def load_json(self):
        """Loads JSON content from the provided URI."""
        try:
            with open(self.json_uri, 'r') as json_file:
                self.json_data = json.load(json_file)
                print("JSON Loaded Successfully!")
        except FileNotFoundError:
            print(f"Error: JSON file not found at {self.json_uri}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading JSON content: {e}")
            sys.exit(1)

    def extract_pdf_text(self):
        """Extracts text from the PDF file using Document AI."""
        print(f"Processing PDF: {self.pdf_uri}")
        credentials, project = google.auth.default(
            quota_project_id="qwiklabs-gcp-00-5fdb2d368561",
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        opts = ClientOptions(api_endpoint=f"eu-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(credentials=credentials, client_options=opts)

        with open(self.pdf_uri, "rb") as fh:
            pdf_file = io.BytesIO(fh.read())

        pdf_bytes = pdf_file.getvalue()
        raw_document = documentai.RawDocument()
        raw_document.content = pdf_bytes
        raw_document.mime_type = "application/pdf"

        request = documentai.ProcessRequest(
            raw_document=raw_document,
            name=f"projects/1083979906926/locations/eu/processors/b2f4418046bae89d:process"
        )

        result = client.process_document(request=request)
        document = result.document

        self.pdf_text = document.text
        print("PDF Processed Successfully!")

    def validate_and_correct_json(self, max_attempts=3):
        """Validates and corrects the JSON data based on the extracted PDF text."""
        attempts = 0
        corrected = False

        while attempts < max_attempts:
            print(f"\n🔍 Attempt {attempts + 1}")
            print("**Agent 1 (Verifier):**")

            # Step 1: Verify the JSON
            """prompt_verification = PROMPT_VERIFICAR.format(json_data=self.json_data, pdf_text=self.pdf_text)
            result = self.agente_verificador.generate_response(prompt_verification)

            if "OK" in result:
                print("✅ JSON successfully validated by the Verifier agent.")
                if corrected:
                    print(f"Result reached in interaction: {attempts}")
                    return self.json_data  # JSON is correct

            print(f"⚠️ Errors detected: {result}")

            # Step 2: Try to correct
            print("**Agent 2 (Corrector):**")
            prompt_correction = PROMPT_CORREGIR.format(json_data=self.json_data, pdf_text=self.pdf_text, errores=result)
            corrected_json = self.agente_corregidor.generate_response(prompt_correction)
            corrected = True

            if "ERROR" in corrected_json:
                print("❌ Failed to complete the JSON in this attempt.")
            elif "OK" in corrected_json:
                print("✅ JSON successfully corrected by the Corrector agent.")
                self.json_data = corrected_json  # Use the new corrected version
            else:
                print("---Could not detect status---!")"""

            attempts += 1

        print("\n🚨 Maximum attempts reached. Could not validate the JSON.")
        return {"error": "Could not complete the JSON with available information after several attempts."}


class VertexAI:
    def __init__(self, model, system_instruction="", temperature=0):
        self.generation_config = {"temperature": temperature}
        self.model = GenerativeModel(
            model_name=model,
            system_instruction=[system_instruction],
            generation_config=self.generation_config,
        )

    def generate_response(self, prompt: str):
        response = self.model.generate_content(prompt)
        return response.text


# === Prompts ===
PROMPT_VERIFICAR = """
You are an expert analyst in extracting and validating structured data from PDF documents, ensuring the JSON matches the content of the PDF.

---

### **Inputs:**
- **Extracted JSON:** `{json_data}`
- **Original PDF Text:** `{pdf_text}`

---

### **Instructions:**
1. Carefully analyze the content of the provided PDF.
2. Review the JSON extracted from the PDF.
3. Correct the JSON according to the information in the PDF and the Correction Rules.
4. Ensure that all fields conform to the specified formats.
5. If any field contains `"NOT_FOUND"`, the JSON is **not validated** so return `"ERROR"` and provide a detailed list of missing or incorrect fields.
6. If the JSON is **fully validated**, return `"OK"`.
7. If the JSON is **not validated**, return `"ERROR"` and provide a detailed list of missing or incorrect fields.


### **Correction Rules:**
- **ISIN**: Unique fund identifier (12 alphanumeric characters). If missing, return `"NOT_FOUND"`.  
- **SHARES_QTY**: ALWAYS respect the original sign in the PDF for each extracted quantity WITHOUT EXCEPTION. Ensure of extract the exact number of decimal digits for each quantity.
  - Keep the original sign and decimal places.
  - If missing, return `"NOT_FOUND"`.  
  - **Format:** Decimal number (e.g., `129.13`, `-750.00`).
  - If PDF contains a positive number, do not think if that is correct, respect the sign.
- **ACCOUNT_IN**: Account ID, account number. It is the number that identifies the account where the shares are transferred (To:). If you can't find the Account ID, return  `"NOT_FOUND"`.  
- **ACCOUNT_OUT**: Account ID, account number. It is the number that identifies the account from which the shares are transferred (From:). If you can't find the Account ID, return  `"NOT_FOUND"`.  
- **TRANSFERTYPE**:  
  - If the document is a **Transfer In**, return `"IN"`.  
  - If the document is a **Transfer Out**, return `"OUT"`.  
  - If unclear, return `"NOT_FOUND"`.  
- **TRANSFER_REFERENCE**: Transaction or reference number. If missing, return `"NOT_FOUND"`.  
- **SETTLEMENT_DATE**: Settlement date of the transaction.  
  - **Format:** `DD-MM-YYYY`.  
  - If missing, return `"NOT_FOUND"`.  
- **NAVDATE**: Date when the **Net Asset Value (NAV)** per share was calculated.  
  - Look for phrases like `"Date of NAV"` or `"NAV Date"`.  
  - Ensure it is a **date**, not a price or quantity.  
  - **Format:** `DD-MM-YYYY`.  
  - If missing, return `"NOT_FOUND"`.  
- **PAGE_NUMBER**: Page where the transaction is located.  
  - Look for `"Extraction done page number X"`.  
  - If missing, return `"NOT_FOUND"`.  


**The PDF is the ultimate source of truth.** Always prioritize the PDF over the original JSON.  
"""

PROMPT_CORREGIR = """
Corrige el siguiente JSON basándote en el texto original del PDF.

Errores detectados:
{errores}

Si puedes completar los campos, genera un nuevo JSON corregido y responde 'OK'. 
Si no puedes corregirlo completamente, responde 'ERROR'.

JSON actual:
{json_data}

Texto del PDF:
{pdf_text}

Instructions:
1. Analyze the content of the provided PDF.
2. Analyze if the data in the provided JSON corresponds exactly to the content of the PDF.
3. If Agent 2 made suggestions, analyze them and apply them if correct.

General Rules:
- ISIN: Unique fund identifier (12 alphanumeric characters). If not found, use "NOT_FOUND".
- SHARES_QTY: ALWAYS respect the original sign in the PDF for each extracted quantity WITHOUT EXCEPTION. If not found, use "NOT_FOUND". Format: number with decimal point (e.g., 129.13, -750.00).
- ACCOUNT_IN: ID of the account where the shares are transferred (To:). If not found, use "NOT_FOUND".
- ACCOUNT_OUT: ID of the account from where the shares are transferred (From:). If not found, use "NOT_FOUND".
- TRANSFERTYPE: Transfer type. If the document is Transfer in, return "IN". If the document is Transfer out, return "OUT". If you can't find the Transfer Type, return "NOT_FOUND".
- TRANSFER_REFERENCE: Transaction or reference number. If not found, use "NOT_FOUND".
- SETTLEMENT_DATE: Settlement date. Format: DD-MM-YYYY. If not found, use "NOT_FOUND".
- NAVDATE: Date when the Net Asset Value (NAV) per share used for this transaction was calculated. Look for phrases like 'Date of NAV' or 'NAV Date'. Ensure it is a *date*, not a price or quantity. Format: DD-MM-YYYY. If not found, use "NOT_FOUND".
- PAGE_NUMBER: Page number where the transaction is located. Look for 'Extraction done page number X'. If not found, use "NOT_FOUND".

"""


# === Main Function for CLI ===
def main(pdf_content):
    print("Llame a VALIDATION "+pdf_content)
    """if len(sys.argv) != 3:
        print("Usage: python script.py <json_uri> <pdf_uri>")
        sys.exit(1)

    json_uri = sys.argv[1]
    pdf_uri = sys.argv[2]

    # Initialize the JSONValidator with the provided URIs
    validator = JSONValidator(json_uri=json_uri, pdf_uri=pdf_uri)
    
    # Load JSON
    validator.load_json()

    # Extract PDF text
    validator.extract_pdf_text()"""

    validator = JSONValidator(pdf_content=pdf_content)

    # Validate and Correct JSON
    result = validator.validate_and_correct_json()
    
    return result


if __name__ == "__main__":
    main()
