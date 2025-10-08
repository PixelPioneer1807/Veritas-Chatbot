# Multimodal Document Analysis Chatbot

Veritas is an intelligent chatbot designed to help you understand your documents in a more intuitive and powerful way. It goes beyond simple text-based Q&A by incorporating multimodal capabilities, allowing it to analyze both the text and the visual elements (like charts and graphs) within your PDFs. With integrated web search and voice input, Veritas provides a comprehensive and interactive document analysis experience.

## Features

-   **PDF Document Upload:** Easily upload your PDF documents for analysis.
-   **Multimodal RAG Pipeline:** Veritas uses a Retrieval-Augmented Generation (RAG) pipeline that can process and understand both text and images.
-   **Visual Question Answering (VQA):** Ask questions about charts, graphs, and other visual data within your documents.
-   **Text-Based Q&A:** Get answers to your questions based on the textual content of your documents.
-   **Web Search Integration:** For questions that can't be answered from the document alone, Veritas can search the web to provide a more complete answer.
-   **Voice Input:** Use your voice to ask questions with real-time transcription.
-   **Interactive PDF Viewer:** When the chatbot provides an answer, it can display the relevant page of the PDF for your reference.
-   **Citations:** Veritas provides citations for the information it uses, so you can easily track the source of the answer.

## Tech Stack

### Backend

-   **Python**
-   **FastAPI:** For building the RESTful API.
-   **Pinecone:** For vector storage and similarity search.
-   **SentenceTransformers:** For creating text embeddings.
-   **Groq:** For fast LLM inference.
-   **Google Gemini:** For visual language model (VLM) capabilities.
-   **Serper:** For web search.
-   **Deepgram:** For real-time speech-to-text.
-   **PyMuPDF (fitz):** For PDF parsing and image extraction.

### Frontend

-   **Next.js:** For the React framework.
-   **React:** For building the user interface.
-   **Tailwind CSS:** For styling.

## System Architecture

The application is divided into a frontend and a backend.

1.  **File Upload:** The user uploads a PDF file through the Next.js frontend.
2.  **Backend Processing:** The FastAPI backend receives the file.
3.  **PDF Parsing:** The `document_processor.py` script extracts text and images from the PDF.
4.  **Embedding and Indexing:** The extracted text is converted into vector embeddings using `SentenceTransformers` and stored in a Pinecone vector database.
5.  **User Query:** The user asks a question (either by typing or by voice).
6.  **Query Processing:**
    -   If the query is text-based, the backend creates an embedding of the query and searches the Pinecone database for relevant text chunks.
    -   If the query is determined to be about a visual element, the `vlm_handler.py` script uses Google Gemini to analyze the relevant image.
    -   If the web search option is enabled, the `web_search.py` script uses the Serper API to get relevant information from the web.
7.  **Response Generation:** The retrieved text, VLM output, and web search results are combined into a comprehensive context that is passed to the Groq API with a prompt.
8.  **Streaming to Frontend:** The response from the LLM is streamed back to the frontend and displayed to the user.

## Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

-   **Python 3.8+**
-   **Node.js and npm (or yarn/pnpm/bun)**
-   **Git**

### Backend Setup

1.  **Clone the repository:**

    ```bash
    git clone [https://github.com/pixelpioneer1807/veritas-chatbot.git](https://github.com/pixelpioneer1807/veritas-chatbot.git)
    cd veritas-chatbot/backend
    ```

2.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file:**

    Create a file named `.env` in the `backend` directory and add your API keys:

    ```
    PINECONE_API_KEY="YOUR_PINECONE_API_KEY"
    GROQ_API_KEY="YOUR_GROQ_API_KEY"
    GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
    SERPER_API_KEY="YOUR_SERPER_API_KEY"
    DEEPGRAM_API_KEY="YOUR_DEEPGRAM_API_KEY"
    ```

5.  **Run the backend server:**

    ```bash
    uvicorn main:app --reload
    ```

    The backend will be running at `http://127.0.0.1:8000`.

### Frontend Setup

1.  **Navigate to the frontend directory:**

    ```bash
    cd ../frontend
    ```

2.  **Install dependencies:**

    ```bash
    npm install
    ```

3.  **Run the frontend development server:**

    ```bash
    npm run dev
    ```

    The frontend will be running at `http://localhost:3000`.

## Usage

1.  **Open your browser** and go to `http://localhost:3000`.
2.  **Upload a PDF document** by clicking the "Upload" button.
3.  **Ask a question** about the document in the input field or by using the "Record" button for voice input.
4.  **View the response** from the chatbot. If the response is based on a specific page, you can click on the page number to view it in the interactive PDF viewer.

### Key Files

-   `backend/main.py`: The main FastAPI application file that handles API routes for file upload and chat.
-   `backend/document_processor.py`: Contains the logic for processing uploaded PDF files, extracting text and images.
-   `backend/vector_store.py`: Manages the embedding of text chunks and interaction with the Pinecone vector database.
-   `backend/llm_handler.py`: Interacts with the Groq API to get responses from the language model.
-   `backend/vlm_handler.py`: Interacts with the Google Gemini VLM to analyze images.
-   `backend/web_search.py`: Handles web searches using the Serper API.
-   `frontend/src/app/page.js`: The main page of the Next.js application, containing the chat interface and logic for interacting with the backend.

## Future Improvements

-   **Support for more document types:** Add support for `.docx`, `.pptx`, and other common file formats.
-   **More advanced VLM capabilities:** Implement more complex visual analysis, such as comparing multiple charts or understanding handwritten notes.
-   **User authentication:** Add a user authentication system to allow users to save and manage their documents.
-   **Improved UI/UX:** Enhance the user interface with features like chat history and document management.
-   **Deployment:** Provide instructions for deploying the application to a cloud platform.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
