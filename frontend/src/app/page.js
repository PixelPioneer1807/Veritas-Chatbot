// frontend/src/app/page.js

"use client";

import { useState, useRef } from "react";

export default function Home() {
  const [messages, setMessages] = useState([
    { role: "bot", content: "Hello! Upload a document and I'll answer your questions about it." }
  ]);
  const [input, setInput] = useState("");
  const [pdfUrl, setPdfUrl] = useState(null);
  const [currentPage, setCurrentPage] = useState(null);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const fileInputRef = useRef(null);
  const [isRecording, setIsRecording] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState(null);

  const deepgramSocketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  const DEEPGRAM_API_KEY = "";

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Store PDF for viewing
    const fileUrl = URL.createObjectURL(file);
    setPdfUrl(fileUrl);
    setUploadedFileName(file.name);

    const formData = new FormData();
    formData.append("file", file);

    const uploadingMessage = { role: "bot", content: `Uploading "${file.name}"...` };
    setMessages(prevMessages => [...prevMessages, uploadingMessage]);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("File upload failed");

      const result = await response.json();
      const successMessage = { role: "bot", content: result.message };
      setMessages(prevMessages => [...prevMessages.slice(0, -1), successMessage]);

    } catch (error) {
      console.error("Upload error:", error);
      const errorMessage = { role: "bot", content: "Sorry, there was an error uploading the file." };
      setMessages(prevMessages => [...prevMessages.slice(0, -1), errorMessage]);
    }
  };

  const handleSend = async () => {
    if (input.trim()) {
      const userMessage = { role: "user", content: input };
      const newMessages = [...messages, userMessage];
      setMessages(newMessages);
      setInput("");
      try {
        const response = await fetch("http://127.0.0.1:8000/api/chat", {
          method: "POST", 
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: input }),
        });
        if (!response.ok) throw new Error("Network response was not ok");
        const botResponse = await response.json();
        setMessages([...newMessages, botResponse]);
      } catch (error) {
        console.error("Fetch error:", error);
        const errorMessage = { role: "bot", content: "Sorry, I'm having trouble connecting." };
        setMessages([...newMessages, errorMessage]);
      }
    }
  };

  const handlePageClick = (pageNumber) => {
    setCurrentPage(pageNumber);
    setShowPdfViewer(true);
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    
    if (deepgramSocketRef.current) {
      deepgramSocketRef.current.close();
      deepgramSocketRef.current = null;
    }
    
    mediaRecorderRef.current = null;
    setIsRecording(false);
  };

  const toggleRecording = async () => {
    if (isRecording) {
      stopRecording();
    } else {
      try {
        // Check API key first
        if (!DEEPGRAM_API_KEY || DEEPGRAM_API_KEY.trim() === "") {
          alert("Please add your Deepgram API key to enable voice recording!");
          return;
        }

        console.log("Requesting microphone access...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        
        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm'
        });
        mediaRecorderRef.current = mediaRecorder;

        console.log("Connecting to Deepgram...");
        const socket = new WebSocket(
          'wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true',
          ['token', DEEPGRAM_API_KEY]
        );
        deepgramSocketRef.current = socket;

        socket.onopen = () => {
          console.log('✓ Deepgram WebSocket connected');
          setIsRecording(true);
          
          mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
              socket.send(event.data);
            }
          };
          
          mediaRecorder.start(250);
          console.log('✓ Recording started');
        };

        socket.onmessage = (message) => {
          const data = JSON.parse(message.data);
          const transcript = data.channel?.alternatives?.[0]?.transcript;
          if (transcript && transcript.trim() !== '') {
            console.log('Transcript:', transcript);
            setInput(prev => prev + transcript + ' ');
          }
        };

        socket.onerror = (error) => {
          console.error('Deepgram WebSocket error:', error);
          alert('Connection to Deepgram failed. Please check:\n1. Your API key is correct\n2. You have an active internet connection\n3. Check browser console for details');
          stopRecording();
        };

        socket.onclose = (event) => {
          console.log('Deepgram WebSocket closed:', event.code, event.reason);
          if (event.code !== 1000) {
            // Abnormal closure
            console.error('Abnormal WebSocket closure');
          }
          stopRecording();
        };

      } catch (error) {
        console.error("Failed to start recording:", error);
        if (error.name === 'NotAllowedError') {
          alert("Microphone access denied. Please allow microphone access in your browser settings.");
        } else if (error.name === 'NotFoundError') {
          alert("No microphone found. Please connect a microphone and try again.");
        } else {
          alert("Failed to start recording: " + error.message);
        }
        stopRecording();
      }
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Chat Section */}
      <div className={`flex flex-col transition-all duration-300 ${showPdfViewer ? 'w-1/2' : 'w-full'}`}>
        <header className="p-4 border-b bg-white shadow-sm">
          <h1 className="text-xl font-semibold text-gray-800">Veritas Chatbot</h1>
          {uploadedFileName && (
            <p className="text-sm text-gray-500 mt-1">Document: {uploadedFileName}</p>
          )}
        </header>
        
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, index) => (
            <div key={index} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'bot' && (
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold flex-shrink-0">
                  V
                </div>
              )}
              <div className={`flex flex-col gap-2 max-w-[70%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`p-3 rounded-lg ${
                  msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'
                }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                
                {msg.role === 'bot' && msg.citations && msg.citations.length > 0 && (
                  <div className="flex items-center gap-2 px-2 flex-wrap">
                    <span className="text-xs text-gray-500 font-medium">Sources:</span>
                    <div className="flex flex-wrap gap-1">
                      {msg.citations.map((page, idx) => (
                        <button
                          key={idx}
                          onClick={() => handlePageClick(page)}
                          className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition-colors cursor-pointer"
                          title={`Click to view Page ${page}`}
                        >
                          Page {page}
                        </button>
                      ))}
                    </div>
                    
                    {msg.used_vlm && (
                      <span 
                        className="inline-flex items-center px-2 py-1 text-xs font-medium bg-purple-100 text-purple-700 rounded-full"
                        title={`Analyzed visual content on pages: ${msg.vlm_pages?.join(', ')}`}
                      >
                        Chart Analysis
                      </span>
                    )}
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-white font-bold flex-shrink-0">
                  U
                </div>
              )}
            </div>
          ))}
        </main>

        <footer className="p-4 border-t bg-white shadow-lg">
          <div className="flex items-center gap-3">
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              className="hidden" 
              accept=".pdf" 
            />
            <button 
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium"
              onClick={() => fileInputRef.current.click()}
            >
              Upload
            </button>
            <button
              className={`px-4 py-2 rounded-lg transition-colors font-medium ${
                isRecording 
                  ? 'bg-red-500 text-white hover:bg-red-600' 
                  : 'bg-green-500 text-white hover:bg-green-600'
              }`}
              onClick={toggleRecording}
            >
              {isRecording ? 'Stop' : 'Record'}
            </button>
            <input
              type="text"
              placeholder="Type your message..."
              className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            />
            <button 
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
              onClick={handleSend}
            >
              Send
            </button>
          </div>
        </footer>
      </div>

      {/* PDF Viewer Section */}
      {showPdfViewer && pdfUrl && (
        <div className="w-1/2 border-l bg-white flex flex-col">
          <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-800">Document Viewer</h2>
              {currentPage && (
                <span className="text-sm text-gray-600">Page {currentPage}</span>
              )}
            </div>
            <button
              onClick={() => setShowPdfViewer(false)}
              className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
            >
              Close
            </button>
          </div>
          <div className="flex-1 overflow-auto">
            <iframe
              src={`${pdfUrl}#page=${currentPage || 1}&view=FitH`}
              className="w-full h-full"
              title="PDF Viewer"
            />
          </div>
        </div>
      )}
    </div>
  );
}