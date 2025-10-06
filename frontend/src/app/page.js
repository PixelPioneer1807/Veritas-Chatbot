// frontend/src/app/page.js
"use client";

import { useState, useRef, useEffect } from "react";

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
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(true);
  const [isMicrophoneOn, setIsMicrophoneOn] = useState(false);

  const deepgramSocketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);

  // IMPORTANT: Replace with your actual Deepgram API key
  const DEEPGRAM_API_KEY = ""; 

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (deepgramSocketRef.current) {
        deepgramSocketRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

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
          body: JSON.stringify({ 
            message: input,
            search_web: isWebSearchEnabled 
          }),
        });
        if (!response.ok) throw new Error("Network response was not ok");
        const botResponse = await response.json();
        setMessages([...newMessages, botResponse]);
        
        if (botResponse.citations && botResponse.citations.length > 0 && pdfUrl) {
          const firstPage = botResponse.citations[0];
          setCurrentPage(firstPage);
          setShowPdfViewer(true);
        }
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

  const toggleMicrophone = async () => {
    if (isMicrophoneOn) {
      console.log("Turning OFF microphone...");
      
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      
      if (audioContextRef.current) {
        await audioContextRef.current.close();
        audioContextRef.current = null;
      }
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      
      if (deepgramSocketRef.current && deepgramSocketRef.current.readyState === WebSocket.OPEN) {
        deepgramSocketRef.current.send(JSON.stringify({ type: "CloseStream" }));
        deepgramSocketRef.current.close(1000, 'User turned off microphone');
      }
      deepgramSocketRef.current = null;
      
      setIsMicrophoneOn(false);
      console.log("Microphone turned OFF");
      
    } else {
      if (!DEEPGRAM_API_KEY) {
        alert("Please add your Deepgram API key to enable voice recording!");
        return;
      }
      
      try {
        console.log("Turning ON microphone...");
        
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            channelCount: 1,
            sampleRate: 16000,
          } 
        });
        streamRef.current = stream;
        
        const socket = new WebSocket(
          'wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1&model=nova-2&smart_format=true&interim_results=true',
          ['token', DEEPGRAM_API_KEY]
        );
        deepgramSocketRef.current = socket;

        socket.onopen = () => {
          console.log("✓ Deepgram WebSocket connected");
          setIsMicrophoneOn(true);
          
          const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
          audioContextRef.current = audioContext;
          
          const source = audioContext.createMediaStreamSource(stream);
          const processor = audioContext.createScriptProcessor(4096, 1, 1);
          processorRef.current = processor;
          
          processor.onaudioprocess = (e) => {
            if (socket.readyState === WebSocket.OPEN) {
              const inputData = e.inputBuffer.getChannelData(0);
              
              const int16Data = new Int16Array(inputData.length);
              for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
              }
              
              socket.send(int16Data.buffer);
            }
          };
          
          source.connect(processor);
          processor.connect(audioContext.destination);
        };

        socket.onmessage = (message) => {
          const data = JSON.parse(message.data);
          
          if (data.type === 'Results' && data.is_final) {
            const transcript = data.channel?.alternatives?.[0]?.transcript;
            if (transcript && transcript.trim()) {
              console.log("Final transcript:", transcript);
              setInput(prev => prev + transcript + ' ');
            }
          }
        };
        
        socket.onerror = (error) => {
          console.error('Deepgram WebSocket error:', error);
          setIsMicrophoneOn(false);
        };

        socket.onclose = (event) => {
          console.log('Deepgram WebSocket closed:', event.code, event.reason);
          setIsMicrophoneOn(false);
        };

      } catch (error) {
        console.error("Failed to start microphone:", error);
        alert("Could not access microphone. Please check permissions.");
      }
    }
  };

  const toggleRecording = () => {
    if (!isMicrophoneOn) {
      alert("Please turn on the microphone first!");
      return;
    }
    setIsRecording(!isRecording);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <div className={`flex flex-col transition-all duration-300 ${showPdfViewer ? 'w-1/2' : 'w-full'}`}>
        <header className="p-4 border-b bg-white shadow-sm">
          <h1 className="text-xl font-semibold text-gray-800">MultiModal Document Chatbot</h1>
          {uploadedFileName && (
            <p className="text-sm text-gray-500 mt-1">Document: {uploadedFileName}</p>
          )}
        </header>
        
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, index) => (
            <div key={index} className={`flex items-start gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'bot' && (
                <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold flex-shrink-0">V</div>
              )}
              <div className={`flex flex-col gap-2 max-w-[70%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`p-3 rounded-lg ${msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-800'}`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
                
                {/* NEW: Separated RAG and Web Responses */}
                {msg.role === 'bot' && msg.response_type === 'document_query' && (
                  <div className="w-full space-y-3">
                    {/* RAG Response Section */}
                    {msg.rag_response && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-semibold text-blue-700">📄 FROM DOCUMENT</span>
                        </div>
                        <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.rag_response}</p>
                      </div>
                    )}
                    
                    {/* Web Response Section */}
                    {msg.web_response && msg.web_response !== msg.rag_response && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-semibold text-green-700">🌐 WITH WEB SEARCH</span>
                        </div>
                        <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.web_response}</p>
                        
                        {/* Web Sources */}
                        {msg.web_sources && msg.web_sources.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-green-200">
                            <span className="text-xs font-medium text-green-700 block mb-2">Web Sources:</span>
                            <div className="space-y-1">
                              {msg.web_sources.map((source, idx) => (
                                <a 
                                  key={idx} 
                                  href={source.link} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="block text-xs text-blue-600 hover:text-blue-800 hover:underline truncate"
                                  title={source.title}
                                >
                                  {idx + 1}. {source.title}
                                </a>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Document Citations */}
                {msg.role === 'bot' && msg.citations && msg.citations.length > 0 && (
                  <div className="flex items-center gap-2 px-2 flex-wrap">
                    <span className="text-xs text-gray-500 font-medium">Document Pages:</span>
                    <div className="flex flex-wrap gap-1">
                      {msg.citations.map((page, idx) => (
                        <button key={idx} onClick={() => handlePageClick(page)} className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition-colors cursor-pointer" title={`Click to view Page ${page}`}>
                          Page {page}
                        </button>
                      ))}
                    </div>
                    {msg.used_vlm && (
                      <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-purple-100 text-purple-700 rounded-full" title={`Analyzed visual content on pages: ${msg.vlm_pages?.join(', ')}`}>
                        📊 Chart Analysis
                      </span>
                    )}
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-white font-bold flex-shrink-0">U</div>
              )}
            </div>
          ))}
        </main>

        <footer className="p-4 border-t bg-white shadow-lg">
          <div className="flex items-center gap-3">
            <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept=".pdf" />
            <button className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium" onClick={() => fileInputRef.current.click()}>
              Upload
            </button>
            
            <button 
              className={`px-4 py-2 rounded-lg transition-colors font-medium flex items-center gap-2 ${
                isMicrophoneOn 
                  ? 'bg-green-500 text-white hover:bg-green-600' 
                  : 'bg-gray-400 text-white hover:bg-gray-500'
              }`} 
              onClick={toggleMicrophone}
            >
              {isMicrophoneOn ? '🎤 OFF' : '🎤 ACTIVATE'}
            </button>
            
            <input 
              type="text" 
              placeholder={isMicrophoneOn ? "Speak or type your message..." : "Type your message..."} 
              className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-black" 
              value={input} 
              onChange={(e) => setInput(e.target.value)} 
              onKeyDown={handleKeyDown} 
            />
            <button className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium" onClick={handleSend}>
              Send
            </button>
          </div>
          <div className="flex items-center justify-center gap-2 mt-2">
            <input type="checkbox" id="web-search-toggle" checked={isWebSearchEnabled} onChange={(e) => setIsWebSearchEnabled(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer" />
            <label htmlFor="web-search-toggle" className="text-sm text-gray-600 select-none cursor-pointer">
              Enable Web Search
            </label>
            {isMicrophoneOn && (
              <span className="text-xs text-green-600 font-medium ml-4">
                🔴 Live transcription active
              </span>
            )}
          </div>
        </footer>
      </div>

      {showPdfViewer && pdfUrl && currentPage && (
        <div className="w-1/2 border-l bg-white flex flex-col">
          <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-800">📄 Source Document</h2>
              <span className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-full font-medium">Page {currentPage}</span>
            </div>
            <button onClick={() => setShowPdfViewer(false)} className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors font-medium">
              ✕ Close
            </button>
          </div>
          <div className="px-4 py-2 bg-yellow-50 border-b border-yellow-200">
            <p className="text-sm text-yellow-800"><strong>💡 This page contains the information used to answer your question</strong></p>
          </div>
          <div className="flex-1 overflow-hidden bg-gray-100 flex items-center justify-center p-4">
            <div className="w-full h-full relative">
              <div className="absolute inset-0 border-4 border-yellow-400 opacity-50 pointer-events-none z-10 animate-pulse"></div>
              <iframe key={currentPage} src={`${pdfUrl}#page=${currentPage}&view=FitH&toolbar=0&navpanes=0&scrollbar=0`} className="w-full h-full border-0 shadow-lg" title={`PDF Page ${currentPage}`} style={{ backgroundColor: 'white' }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}