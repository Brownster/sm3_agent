import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Wrench } from 'lucide-react';
import { chatApi } from '@/services/api';
import type { Message, ToolCall } from '@/types';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input;
    setInput('');
    setIsLoading(true);

    try {
      // Create assistant message placeholder
      const assistantMessageId = `${Date.now()}-assistant`;
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
        toolCalls: [],
        suggestions: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      let accumulatedContent = '';
      let toolCalls: ToolCall[] = [];
      let suggestions: string[] = [];

      // Stream the response
      for await (const chunk of chatApi.stream({
        message: messageText,
        session_id: sessionId,
      })) {
        if (chunk.type === 'token' && chunk.message) {
          accumulatedContent += chunk.message;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: accumulatedContent }
                : msg
            )
          );
        } else if (chunk.type === 'tool') {
          const toolCall: ToolCall = {
            tool: chunk.tool || 'unknown',
            arguments: chunk.arguments || {},
            result: chunk.result,
          };
          toolCalls.push(toolCall);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, toolCalls: [...toolCalls] }
                : msg
            )
          );
        } else if (chunk.type === 'complete') {
          // Final message might include suggestions
          if (chunk.message) {
            accumulatedContent = chunk.message;
          }
        } else if (chunk.type === 'error') {
          accumulatedContent = `Error: ${chunk.message || 'An error occurred'}`;
        }
      }

      // Mark streaming as complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false, suggestions }
            : msg
        )
      );
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: `${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, an error occurred while processing your request. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex flex-col">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center">
            <div>
              <h2 className="text-2xl font-bold mb-2">Welcome to Sabio Monitoring Agent</h2>
              <p className="text-gray-400 mb-6">
                Ask me anything about your monitoring dashboards, metrics, and logs.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {[
                  'Show me all datasources',
                  'What dashboards are available?',
                  'Query error rate in the last hour',
                  'Show recent logs from production',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-sm transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-3xl rounded-lg px-4 py-3 ${
                  message.role === 'user'
                    ? 'bg-orange-500/20 text-white'
                    : 'bg-gray-800 text-gray-100'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>

                {/* Tool calls */}
                {message.toolCalls && message.toolCalls.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {message.toolCalls.map((toolCall, idx) => (
                      <div
                        key={idx}
                        className="bg-gray-900/50 border border-gray-700 rounded p-2 text-sm"
                      >
                        <div className="flex items-center gap-2 text-blue-400 mb-1">
                          <Wrench className="w-3 h-3" />
                          <span className="font-mono">{toolCall.tool}</span>
                        </div>
                        {toolCall.result && (
                          <div className="text-xs text-gray-400 mt-1 max-h-32 overflow-y-auto">
                            <pre className="whitespace-pre-wrap break-words">
                              {typeof toolCall.result === 'string'
                                ? toolCall.result
                                : JSON.stringify(toolCall.result, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Suggestions */}
                {message.suggestions && message.suggestions.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {message.suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs transition-colors"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}

                <div className="text-xs text-gray-500 mt-2 flex items-center gap-2">
                  <span>{message.timestamp.toLocaleTimeString()}</span>
                  {message.isStreaming && (
                    <span className="flex items-center gap-1">
                      <span className="animate-pulse">●</span>
                      <span>streaming</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-lg px-4 py-3">
              <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your monitoring metrics, dashboards, or logs..."
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-orange-500 transition-colors"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="bg-orange-500 hover:bg-orange-600 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-lg px-6 py-3 transition-colors flex items-center gap-2"
        >
          <Send className="w-5 h-5" />
          <span>Send</span>
        </button>
      </form>
    </div>
  );
}
