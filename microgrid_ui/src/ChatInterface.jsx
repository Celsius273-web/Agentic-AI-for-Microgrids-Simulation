import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const ChatInterface = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I'm the Microgrid Agent. I can help you manage your microgrid system, analyze data, and provide insights. What would you like to know?",
      sender: 'agent',
      agent: 'microgrid',
      timestamp: new Date().toISOString()
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('microgrid');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      text: inputMessage,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Get auth token from localStorage (you'll need to implement auth)
      const token = localStorage.getItem('authToken') || 'demo-token';
      
      const response = await axios.post('http://localhost:8002/chat', {
        message: inputMessage,
        agent: selectedAgent
      }, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const agentMessage = {
        id: Date.now() + 1,
        text: response.data.response,
        sender: 'agent',
        agent: response.data.agent,
        timestamp: response.data.timestamp,
      };

      setMessages(prev => [...prev, agentMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage = {
        id: Date.now() + 1,
        text: 'Sorry, I encountered an error processing your message. Please try again.',
        sender: 'agent',
        agent: 'system',
        timestamp: new Date().toISOString(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const getAgentColor = (agent) => {
    const colors = {
      'microgrid': 'bg-blue-500',
      'researcher': 'bg-green-500',
      'monitor': 'bg-amber-500',
      'control': 'bg-purple-500',
      'system': 'bg-red-500'
    };
    return colors[agent] || 'bg-gray-500';
  };

  const getAgentName = (agent) => {
    const names = {
      'microgrid': 'Microgrid Agent',
      'researcher': 'Research Agent',
      'monitor': 'Monitor Agent',
      'control': 'Control Agent',
      'system': 'System'
    };
    return names[agent] || agent;
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-800">
            Microgrid Agent Chat
          </h1>
          
          {/* Agent Selector */}
          <div className="flex items-center space-x-2">
            <label htmlFor="agent-select" className="text-sm font-medium text-gray-700">
              Agent:
            </label>
            <select
              id="agent-select"
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="block px-3 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="microgrid">Microgrid Agent</option>
              <option value="researcher">Research Agent</option>
              <option value="monitor">Monitor Agent</option>
            </select>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.sender === 'user'
                  ? 'bg-gray-500 text-white'
                  : `${getAgentColor(message.agent)} text-white ${
                      message.isError ? 'bg-red-500' : ''
                    }`
              }`}
            >
              {message.sender === 'agent' && (
                <div className="text-xs opacity-90 mb-1">
                  {getAgentName(message.agent)}
                </div>
              )}
              <div className="text-sm">{message.text}</div>
              <div className="text-xs opacity-75 mt-1">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-200 px-4 py-2 rounded-lg max-w-xs lg:max-w-md">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                <span className="text-sm text-gray-600">
                  {getAgentName(selectedAgent)} is thinking...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white p-4">
        <form onSubmit={handleSendMessage} className="flex space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;