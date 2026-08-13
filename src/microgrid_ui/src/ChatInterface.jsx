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
    'w-full max-w-[95%] md:max-w-[90%] lg:max-w-[85%] xl:max-w-[80%]';

  const markdownComponents = {
    p: ({ node, ...props }) => (
      <p className="whitespace-pre-wrap break-words leading-7 mb-2 last:mb-0" {...props} />
    ),
    ul: ({ node, ...props }) => (
      <ul className="list-disc space-y-1 pl-6 my-2 marker:text-cyan-400" {...props} />
    ),
    ol: ({ node, ...props }) => (
      <ol className="list-decimal space-y-1 pl-6 my-2 marker:text-cyan-400" {...props} />
    ),
    li: ({ node, ...props }) => (
      <li className="whitespace-pre-wrap break-words" {...props} />
    ),
    h1: ({ node, children, ...props }) => (
      <h1 className="mb-3 mt-4 text-xl font-bold text-cyan-300 border-b border-cyan-500/30 pb-1" {...props}>
        {children}
      </h1>
    ),
    h2: ({ node, children, ...props }) => (
      <h2 className="mb-2 mt-3 text-lg font-semibold text-cyan-200" {...props}>
        {children}
      </h2>
    ),
    h3: ({ node, children, ...props }) => (
      <h3 className="mb-2 mt-2 text-base font-semibold text-slate-200" {...props}>
        {children}
      </h3>
    ),
    table: ({ node, ...props }) => (
      <div className="my-4 overflow-x-auto rounded-lg border border-slate-700 bg-slate-900/80 shadow-md">
        <table className="w-full border-collapse text-left text-sm" {...props} />
      </div>
    ),
    thead: ({ node, ...props }) => (
      <thead className="bg-slate-800/90 text-cyan-300 border-b border-slate-700" {...props} />
    ),
    tbody: ({ node, ...props }) => (
      <tbody className="divide-y divide-slate-800" {...props} />
    ),
    tr: ({ node, ...props }) => (
      <tr className="hover:bg-slate-800/50 transition-colors" {...props} />
    ),
    th: ({ node, ...props }) => (
      <th className="px-4 py-2.5 font-semibold text-xs uppercase tracking-wider text-cyan-400" {...props} />
    ),
    td: ({ node, ...props }) => (
      <td className="px-4 py-2 text-slate-300 font-mono text-xs" {...props} />
    ),
    code: ({ inline, className, children, ...props }) =>
      inline ? (
        <code
          className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs text-cyan-300 border border-slate-700/50"
          {...props}
        >
          {children}
        </code>
      ) : (
        <code
          className={`${className || ''} block overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-xs leading-6 text-slate-200 border border-slate-800 shadow-inner my-2`}
          {...props}
        >
          {children}
        </code>
      ),
    pre: ({ node, children, ...props }) => (
      <pre className="my-3 overflow-x-auto rounded-xl bg-slate-950 p-0" {...props}>
        {children}
      </pre>
    ),
    blockquote: ({ node, children, ...props }) => (
      <blockquote
        className="my-3 border-l-4 border-cyan-500 bg-cyan-950/20 py-2 px-4 rounded-r text-slate-300 italic"
        {...props}
      >
        {children}
      </blockquote>
    ),
    a: ({ node, children, ...props }) => (
      <a
        className="text-cyan-200 underline underline-offset-2 hover:text-cyan-100"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    ),
    img: () => null,
  };

  const renderMessageContent = (message) => {
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
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-4">
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
        <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
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
            <div className={`${messageBubbleBase} ${messageBubbleSizing} bg-slate-800/90 text-slate-100`}>
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
        <form onSubmit={handleSendMessage} className="mx-auto flex w-full max-w-[1600px] space-x-2">
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
