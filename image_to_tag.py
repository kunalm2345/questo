from PIL import Image
import io
import base64
import google.generativeai as genai

def image_to_base64(image_path):
    """Converts an image to base64 encoding."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string
    except FileNotFoundError:
        return None

def process_image_with_genai(image_path, prompt, api_key, model_name="gemini-2.0-flash"):
    """Sends an image and prompt to Google Generative AI and returns the response."""
    base64_image = image_to_base64(image_path)
    if not base64_image:
        return "Error: Image not found."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    img_data = {
        "mime_type": "image/jpeg",
        "data": base64_image
    }

    try:
        response = model.generate_content([prompt, img_data])
        # Raise an exception for bad responses
        return response.text
    except Exception as e:
        return f"Error: {e}"

# Example usage (replace with your actual API key and image path):
api_key = "AIzaSyDbrnnngoB8LueKwsDG6qOM2R0JLMzVoLM"  # Replace with your actual API key
image_path = "q3.jpg"  # Replace with your image path
prompt = "Describe what is in this image."

result = process_image_with_genai(image_path, prompt, api_key)
print(result)

# Example using a URL instead of a local file.
def process_image_url_with_genai(image_url, prompt, api_key, model_name="gemini-2.0-flash"):
    """Sends an image URL and prompt to Google Generative AI and returns the response."""
    try:
        response = requests.get(image_url)

        img = Image.open(io.BytesIO(response.content))
        if img.mode != "RGB":
            img = img.convert("RGB")
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        img_data = {
            "mime_type": "image/jpeg",
            "data": base64_image
        }

        response = model.generate_content([prompt, img_data])
        
        return response.text

    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error processing image URL: {e}"

# Example usage with image url.
import requests #added this import.
image_url = "https://www.easygifanimator.net/images/samples/video-to-gif-sample.gif"  # Example image url.
api_key = "AIzaSyDbrnnngoB8LueKwsDG6qOM2R0JLMzVoLM" #replace with your api key
prompt = "Transcribe this image."
result2 = process_image_url_with_genai(image_url, prompt, api_key)
print(result2)