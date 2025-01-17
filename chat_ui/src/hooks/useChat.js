import {useState, useEffect} from 'react';
import { API_CONFIG } from '../constants';

export const useChat = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentMessageId, setCurrentMessageId] = useState(null);

  const generateMessageId = (prefix = 'msg') => `${prefix}_${Date.now()}`;

  const createNewConversation = async () => {
    try {
      const newConversationId = `conv_${Date.now()}`;
      const newMessageId = generateMessageId();

      setMessages([]);
      setCurrentMessageId(newMessageId);
      setCurrentConversationId(newConversationId);
      setError(null);

      return {
        messageId: newMessageId,
        conversationId: newConversationId
      };
    } catch (err) {
      console.error('[Debug] Error in createNewConversation:', err);
      throw err;
    }
  };

const handleSend = async (message) => {
  if (isLoading) return;

  try {
    setIsLoading(true);

    let conversationId = currentConversationId;
    if (!conversationId) {
      const newConversation = await createNewConversation();
      conversationId = newConversation.conversationId;
    }

    const messageId = message.message_id || currentMessageId || generateMessageId();

    setMessages(prev => [...prev, {
      id: messageId,
      type: 'user',
      content: message.query || '',
      timestamp: new Date().toLocaleTimeString(),
      attachments: {
        images: message.images?.map(path => ({
          path: path,
          url: `${API_CONFIG.baseUrl_port}/static/upload/images/${path}`,
          preview: `${API_CONFIG.baseUrl_port}/static/upload/images/${path}`
        })) || [],
        files: message.files?.map(path => ({
          path: path,
          url: `${API_CONFIG.baseUrl}/static/upload/files/${path}`,
          name: path.split('/').pop() || path
        })) || []
      }
    }]);

    setMessages(prev => [...prev, {
      id: messageId + '_assistant',
      type: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString(),
      thinkingProcess: ''
    }]);

    const formData = new FormData();
    formData.append('message_id', messageId);
    formData.append('conversation_id', conversationId);
    formData.append('query', message.query || '');
    formData.append('context_length', message.context_length || 10);

    if (message.images?.length > 0) {
      message.images.forEach((path) => {
        if (path) {
          formData.append('images', path);
        }
      });
    }

    if (message.files?.length > 0) {
      message.files.forEach((path) => {
        if (path) {
          formData.append('files', path);
        }
      });
    }

    if (message.rags?.length > 0) {
      message.rags.forEach((ragName) => {
        if (ragName) {
          formData.append('rags', ragName);
        }
      });
    }

    const response = await fetch(`${API_CONFIG.baseUrl}/chat`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);
            setMessages(prev => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];

              switch (data.type) {
                case 'tool_complete':
                  if (lastMessage?.type === 'assistant') {
                    const toolResult = data.result;

                    let images = [];
                    let files = [];

                    if (toolResult.result && typeof toolResult.result === 'string') {
                      const resultValue = toolResult.result.trim();

                      const match = resultValue.match(/output[\/\\](.+)$/);
                      const filePath = match ? match[1].replace(/\\/g, '/') : null;

                      if (filePath) {
                        const encodedPath = encodeURIComponent(filePath);
                        const fileUrl = `${API_CONFIG.baseUrl_port}/static/output/${encodedPath}`;

                        const fileName = filePath.split('/').pop();

                        if (fileName.match(/\.(png|jpg|jpeg|gif)$/i)) {
                          images.push({
                            url: fileUrl,
                            name: fileName
                          });
                        } else {
                          files.push({
                            url: fileUrl,
                            name: fileName
                          });
                        }
                      }
                    }

                    const content = {
                      type: 'mixed',
                      text: toolResult.formatted_result,
                      files: files,
                      images: images
                    };

                    const updatedMessage = {
                      ...lastMessage,
                      content: content
                    };

                    return [...prev.slice(0, -1), updatedMessage];
                  }
                  return prev;

                case 'result':
                  if (lastMessage?.type === 'assistant') {
                    const currentContent = lastMessage.content || {};
                    const updatedMessage = {
                      ...lastMessage,
                      content: typeof currentContent === 'object' ? {
                        ...currentContent,
                        text: data.content
                      } : {
                        type: 'mixed',
                        text: data.content,
                        files: [],
                        images: []
                      }
                    };
                    return [...prev.slice(0, -1), updatedMessage];
                  }
                  return [...prev, {
                    id: messageId,
                    type: 'assistant',
                    content: {
                      type: 'mixed',
                      text: data.content,
                      files: [],
                      images: []
                    }
                  }];

                case 'thinking_process':
                  if (lastMessage?.type === 'assistant') {
                    return [...prev.slice(0, -1), { ...lastMessage, thinkingProcess: data.content }];
                  }
                  return prev;

                case 'error':
                  setError(data.content);
                  return prev;

                default:
                  return prev;
              }
            });
          } catch (e) {
            console.error('Error parsing stream line:', e, line);
          }
        }
      }
    } catch (streamError) {
      console.error('Stream processing error:', streamError);
      throw streamError;
    }

  } catch (err) {
    console.error('Error in handleSend:', err);
    setError(`消息发送失败: ${err.message}`);
  } finally {
    setIsLoading(false);
  }
};

  useEffect(() => {
    return () => {
      messages.forEach(message => {
        if (message.attachments) {
          message.attachments.images?.forEach(img => {
            if (img.preview) URL.revokeObjectURL(img.preview);
          });
          message.attachments.files?.forEach(file => {
            if (file.preview) URL.revokeObjectURL(file.preview);
          });
        }
      });
    };
  }, [messages]);

  return {
    messages,
    isLoading,
    error,
    currentMessageId,
    currentConversationId,
    handleSend,
    createNewConversation,
    setMessages,
    setCurrentMessageId,
    setCurrentConversationId,
    setError
  };
};
