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
image_url = "https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.pinimg.com%2F736x%2Fe0%2Fb8%2F17%2Fe0b8173b2853595a32fa432f2711aa0a.jpg&f=1&nofb=1&ipt=4530884c67a239533acf80977161b0adce9a419ea2b2965080a4af0b5ec4b3ce&ipo=images"  # Example image url.
api_key = "AIzaSyDbrnnngoB8LueKwsDG6qOM2R0JLMzVoLM" #replace with your api key
prompt = "Transcribe this image to extract only the question and its choices. and generate 5 or fewer tags appropriate from the transcription(do not include tags such as quizz,test, and other test names or vague tags) "
result2 = process_image_url_with_genai(image_url, prompt, api_key)
print(result2)