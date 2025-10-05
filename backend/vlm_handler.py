# backend/vlm_handler.py

import os
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
print("Available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"  - {m.name}")
# Initialize the model
model = genai.GenerativeModel('gemini-2.5-flash')

print("VLM configured to use Google Gemini Pro Vision")


def is_visual_query(query: str) -> bool:
    """
    Determines if a query is asking about visual content.
    Now more aggressive to catch chart/data queries.
    """
    visual_keywords = [
        # Direct visual references
        'graph', 'chart', 'image', 'picture', 'figure', 'diagram', 'table',
        'plot', 'visualization', 'shows', 'display', 'illustrate', 'depicts',
        'photo', 'drawing', 'screenshot', 'visual', 'exhibit',
        
        # Chart types
        'bar chart', 'pie chart', 'line graph', 'bar graph', 
        
        # Data/measurement terms (often refer to charts)
        'rating', 'score', 'value', 'number', 'scale', 'measure',
        'data', 'metric', 'statistics', 'percentage', 'trend',
        
        # Common chart-related verbs
        'rate', 'rated', 'scaled', 'measured', 'compare', 'comparison',
        
        # Document-specific
        'barrier', 'issue', 'problem', 'challenge', 'obstacle'
    ]
    
    query_lower = query.lower()
    
    # Check if any keyword is present
    has_keyword = any(keyword in query_lower for keyword in visual_keywords)
    
    # Additional checks for common patterns
    asking_for_list = any(phrase in query_lower for phrase in [
        'what are', 'list', 'name all', 'tell me', 'show me', 'all the'
    ])
    
    has_number_reference = any(word in query_lower for word in [
        'how much', 'how many', 'what number', 'exact', 'specific'
    ])
    
    result = has_keyword or (asking_for_list and has_number_reference)
    
    print(f"[VLM DEBUG] Query: '{query}'")
    print(f"[VLM DEBUG] Has keyword: {has_keyword}")
    print(f"[VLM DEBUG] Asking for list: {asking_for_list}")
    print(f"[VLM DEBUG] Has number reference: {has_number_reference}")
    print(f"[VLM DEBUG] Final decision - Is visual: {result}")
    
    return result


def query_image_with_vlm(image_path: str, question: str) -> str:
    """
    Uses Google Gemini Pro Vision to answer questions about images.
    Excellent for charts, graphs, and complex visuals.
    """
    if not os.path.exists(image_path):
        print(f"[VLM ERROR] Image not found at: {image_path}")
        return "Image not found."
    
    try:
        print(f"[VLM] Loading image from: {image_path}")
        # Load the image
        image = Image.open(image_path)
        print(f"[VLM] Image loaded successfully. Size: {image.size}")
        
        # Create enhanced prompt based on question type
        if any(word in question.lower() for word in ['chart', 'graph', 'bar', 'value', 'number', 'rating', 'score', 'scale']):
            enhanced_prompt = f"""
            You are analyzing a chart or graph from a document. 
            
            Question: {question}
            
            Instructions:
            - Read all values precisely from the chart
            - If there's a scale, read the exact numbers
            - List each item/category with its corresponding value
            - Be specific and accurate with numerical data
            - If you see axis labels or legends, include that information
            """
        else:
            enhanced_prompt = f"""
            Analyze this image from a document and answer the following question accurately:
            
            Question: {question}
            
            Provide detailed, specific information about what you see.
            """
        
        print(f"[VLM] Sending to Gemini...")
        
        # Generate response with CORRECT safety settings format
        response = model.generate_content(
            [enhanced_prompt, image],
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        # Extract the text from response
        if response and hasattr(response, 'text') and response.text:
            answer = response.text.strip()
            print(f"[VLM] ✓ Gemini returned answer ({len(answer)} chars)")
            print(f"[VLM] Answer preview: {answer[:300]}")
            return answer
        else:
            print(f"[VLM] ✗ No text in response")
            print(f"[VLM] Response object: {response}")
            return "Could not extract information from the image."
            
    except Exception as e:
        print(f"[VLM ERROR] Exception occurred: {type(e).__name__}")
        print(f"[VLM ERROR] Error details: {str(e)}")
        
        # Check if it's a safety/blocking issue
        if 'blocked' in str(e).lower() or 'safety' in str(e).lower():
            print(f"[VLM ERROR] Content blocked by safety filters")
            return "Content was blocked by safety filters."
        
        return f"Error processing image: {str(e)}"


def analyze_chart_comprehensively(image_path: str, original_question: str = None) -> str:
    """
    For complex charts, use a comprehensive prompt to extract all information at once.
    This is particularly good for bar charts, pie charts, line graphs, etc.
    """
    if not os.path.exists(image_path):
        print(f"[VLM ERROR] Image not found at: {image_path}")
        return "Image not found."
    
    try:
        print(f"[VLM COMPREHENSIVE] Loading image from: {image_path}")
        image = Image.open(image_path)
        print(f"[VLM COMPREHENSIVE] Image loaded. Size: {image.size}")
        
        comprehensive_prompt = """
        Analyze this chart or graph in complete detail. Please provide:
        
        1. **Title/Topic**: What is the title or main subject of this visualization?
        
        2. **Type**: What type of chart is this (bar chart, line graph, pie chart, etc.)?
        
        3. **Categories and Values**: List EVERY category/item shown with its EXACT numerical value.
           Read the scale carefully and look at where each bar ends. Format as:
           - [Category name]: [exact value from scale]
           - [Category name]: [exact value from scale]
           (continue for all items)
        
        4. **Scale/Units**: What units or scale is being used? What are the min and max values on the axis?
        
        5. **Key Insights**: What are the main patterns or takeaways?
        
        Be extremely precise with numbers - read them directly from the chart axes and bars.
        Look carefully at where each bar or data point aligns with the scale.
        """
        
        if original_question:
            comprehensive_prompt += f"\n\n**Specific Question to Answer**: {original_question}"
        
        print(f"[VLM COMPREHENSIVE] Sending to Gemini with comprehensive prompt...")
        
        response = model.generate_content(
            [comprehensive_prompt, image],
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        if response and hasattr(response, 'text') and response.text:
            answer = response.text.strip()
            print(f"[VLM COMPREHENSIVE] ✓ Gemini returned comprehensive answer ({len(answer)} chars)")
            print(f"[VLM COMPREHENSIVE] Full answer:\n{answer}\n")
            return answer
        else:
            print(f"[VLM COMPREHENSIVE] ✗ No text in response")
            return "Could not analyze chart comprehensively."
            
    except Exception as e:
        print(f"[VLM COMPREHENSIVE ERROR] Exception: {type(e).__name__}")
        print(f"[VLM COMPREHENSIVE ERROR] Details: {str(e)}")
        return f"Error analyzing chart: {str(e)}"


def generate_image_description(image_path: str) -> str:
    """
    Generates a general description of what's in the image.
    Useful for indexing image content.
    """
    if not os.path.exists(image_path):
        return "Visual content"
    
    try:
        image = Image.open(image_path)
        
        prompt = """
        Briefly describe what you see in this image:
        - Type of content (chart, table, diagram, text, photo, etc.)
        - Main topic or subject
        - Key visual elements
        
        Keep it concise (2-3 sentences).
        """
        
        response = model.generate_content([prompt, image])
        
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
        else:
            return "Visual content"
            
    except Exception as e:
        print(f"Error generating image description: {e}")
        return "Visual content"