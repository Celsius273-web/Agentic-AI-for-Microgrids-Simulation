import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

  const messageBubbleBase =
    'w-full rounded-2xl px-4 py-3 shadow-lg ring-1 ring-black/5';

  const messageBubbleSizing =
    'max-w-[92vw] sm:max-w-[80vw] lg:max-w-2xl xl:max-w-4xl';

  const markdownComponents = {
    p: ({ node, ...props }) => (
      <p className="whitespace-pre-wrap break-words leading-7" {...props} />
    ),
    ul: ({ node, ...props }) => (
      <ul className="list-disc space-y-1 pl-5 marker:text-current" {...props} />
    ),
    ol: ({ node, ...props }) => (
      <ol className="list-decimal space-y-1 pl-5 marker:text-current" {...props} />
    ),
    li: ({ node, ...props }) => (
      <li className="whitespace-pre-wrap break-words" {...props} />
    ),
    h1: ({ node, children, ...props }) => (
      <h1 className="mb-2 text-lg font-semibold leading-7" {...props}>
        {children}
      </h1>
    ),
    h2: ({ node, children, ...props }) => (
      <h2 className="mb-2 text-base font-semibold leading-6" {...props}>
        {children}
      </h2>
    ),
    h3: ({ node, children, ...props }) => (
      <h3 className="mb-2 text-sm font-semibold leading-6" {...props}>
        {children}
      </h3>
    ),
    strong: ({ node, children, ...props }) => (
      <strong className="font-semibold text-white" {...props}>
        {children}
      </strong>
    ),
    em: ({ node, children, ...props }) => (
      <em className="italic" {...props}>
        {children}
      </em>
    ),
    a: ({ node, children, ...props }) => (
      <a
        className="font-medium underline decoration-white/50 underline-offset-2 hover:decoration-white"
        target="_blank"
        rel="noreferrer"
        {...props}
      >
        {children}
      </a>
    ),
    code: ({ inline, className, children, ...props }) =>
      inline ? (
        <code
          className="rounded bg-black/25 px-1.5 py-0.5 font-mono text-[0.85em] text-white/95"
          {...props}
        >
          {children}
        </code>
      ) : (
        <code
          className={`${className || ''} block overflow-x-auto rounded-xl bg-slate-950/70 p-3 font-mono text-sm leading-6 text-slate-100`}
          {...props}
        >
          {children}
        </code>
      ),
    pre: ({ node, children, ...props }) => (
      <pre className="my-3 overflow-x-auto rounded-xl bg-slate-950/70 p-0" {...props}>
        {children}
      </pre>
    ),
    blockquote: ({ node, children, ...props }) => (
      <blockquote
        className="border-l-2 border-white/25 pl-3 italic text-white/90"
        {...props}
      >
        {children}
      </blockquote>
    ),
  };

  const renderMessageContent = (message) => {
    const isAgentMessage = message.sender === 'agent';

    if (!isAgentMessage) {
      return (
        <div className="whitespace-pre-wrap break-words text-sm leading-6">
          {message.text}
        </div>
      );
    }

    return (
      <div className="chat-markdown text-sm leading-6">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {message.text}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      {/* Header */}
      <div className="sticky top-0 z-30 border-b border-white/10 bg-slate-900/90 p-4 shadow-lg backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4">
          <h1 className="text-xl font-semibold text-slate-100">
            Microgrid Agent Chat
          </h1>
          
          {/* Agent Selector */}
          <div className="flex items-center space-x-2">
            <label htmlFor="agent-select" className="text-sm font-medium text-slate-300">
              Agent:
            </label>
            <select
              id="agent-select"
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="block rounded-md border border-white/15 bg-slate-800 px-3 py-1 text-sm text-slate-100 shadow-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-cyan-400"
            >
              <option value="microgrid">Microgrid Agent</option>
              <option value="researcher">Research Agent</option>
              <option value="monitor">Monitor Agent</option>
            </select>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="min-h-0 flex-1 overflow-y-auto bg-gradient-to-b from-slate-950 to-slate-900 px-4 py-6">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`${messageBubbleBase} ${messageBubbleSizing} ${
                message.sender === 'user'
                  ? 'bg-slate-700/90 text-slate-50'
                  : `${getAgentColor(message.agent)} bg-opacity-90 text-white ${
                      message.isError ? 'bg-red-500' : ''
                    }`
              }`}
            >
              {message.sender === 'agent' && (
                <div className="mb-1 text-xs font-medium uppercase tracking-wide opacity-90">
                  {getAgentName(message.agent)}
                </div>
              )}
              {renderMessageContent(message)}
              <div className="mt-2 text-xs opacity-75">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[92vw] rounded-2xl bg-slate-800/90 px-4 py-3 text-slate-100 shadow-lg ring-1 ring-black/5 sm:max-w-[80vw] lg:max-w-2xl xl:max-w-4xl">
              <div className="flex items-center space-x-2">
                <div className="h-4 w-4 animate-spin rounded-full border-b-2 border-slate-300"></div>
                <span className="text-sm text-slate-300">
                  {getAgentName(selectedAgent)} is thinking...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 z-30 border-t border-white/10 bg-slate-900/95 p-4 shadow-[0_-8px_30px_rgba(0,0,0,0.25)] backdrop-blur">
        <form onSubmit={handleSendMessage} className="mx-auto flex w-full max-w-7xl space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1 rounded-lg border border-white/15 bg-slate-800 px-4 py-2 text-slate-100 placeholder:text-slate-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-cyan-400 disabled:bg-slate-800/60"
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className="rounded-lg bg-cyan-500 px-6 py-2 text-white transition-colors hover:bg-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-400 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:cursor-not-allowed disabled:bg-slate-600"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;
