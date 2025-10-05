// frontend/src/app/page.js

"use client";

import { useState, useRef } from "react";

export default function Home() {
  const [messages, setMessages] = useState([
    { role: "bot", content: "Hello! Upload a document and I'll answer your questions about it." }
  ]);
  const [input, setInput] = useState("");
  const fileInputRef = useRef(null);
  const [isRecording, setIsRecording] = useState(false);

  const deepgramSocketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  // PUT YOUR DEEPGRAM API KEY HERE
  const DEEPGRAM_API_KEY = "" ;

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

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
        if (!DEEPGRAM_API_KEY || DEEPGRAM_API_KEY === "YOUR_API_KEY_HERE") {
          alert("Please add your Deepgram API key in the code!");
          return;
        }

        console.log("Getting microphone access...");
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: true
        });
        
        streamRef.current = stream;

        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;

        // Create WebSocket connection to Deepgram
        const socket = new WebSocket(
          'wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true',
          ['token', DEEPGRAM_API_KEY]
        );

        deepgramSocketRef.current = socket;

        socket.onopen = () => {
          console.log('Deepgram WebSocket opened');
          
          mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
              socket.send(event.data);
            }
          };
          
          mediaRecorder.start(250);
          console.log('Recording started');
        };

        socket.onmessage = (message) => {
          const data = JSON.parse(message.data);
          console.log('Deepgram response:', data);
          
          const transcript = data.channel?.alternatives?.[0]?.transcript;
          
          if (transcript && transcript.trim() !== '') {
            console.log('Transcript:', transcript);
            setInput(prev => prev + transcript + ' ');
          }
        };

        socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          alert('Error connecting to Deepgram. Check your API key and console.');
          stopRecording();
        };

        socket.onclose = () => {
          console.log('Deepgram WebSocket closed');
        };

        setIsRecording(true);

      } catch (error) {
        console.error("Failed to start recording:", error);
        alert("Failed to access microphone: " + error.message);
        stopRecording();
      }
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="p-4 border-b bg-white">
        <h1 className="text-xl font-semibold">Veritas Chatbot</h1>
      </header>
      
      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'bot' && (
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold">
                V
              </div>
            )}
            <div className={`p-3 rounded-lg max-w-[70%] ${
              msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-white font-bold">
                U
              </div>
            )}
          </div>
        ))}
      </main>

      <footer className="p-4 border-t bg-white">
        <div className="flex items-center gap-3">
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
            accept=".pdf" 
          />
          <button 
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            onClick={() => fileInputRef.current.click()}
          >
            Upload
          </button>
          <button
            className={`px-4 py-2 rounded-lg transition-colors ${
              isRecording 
                ? 'bg-red-500 text-white hover:bg-red-600' 
                : 'bg-green-500 text-white hover:bg-green-600'
            }`}
            onClick={toggleRecording}
          >
            {isRecording ? '⏹ Stop' : '🎤 Record'}
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
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            onClick={handleSend}
          >
            Send
          </button>
        </div>
      </footer>
    </div>
  );
}