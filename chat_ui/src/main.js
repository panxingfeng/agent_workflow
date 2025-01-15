import React, {useState, useRef, useEffect, useCallback, useMemo} from 'react';
import { Clock } from 'lucide-react';
import { useChat } from './hooks/useChat';
import { useFileUpload } from './hooks/useFileUpload';
import { useChatHistory } from './hooks/useChatHistory';
import TopNav from './components/TopNav';
import ChatArea from './components/chat/ChatArea';
import InputArea from './components/input/InputArea';
import { HistoryList } from './components/history/HistoryList';
import './style/animations.css';
import {API_CONFIG} from "./constants";
import MemorySettings from "./components/input/MemorySettings";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 m-4 text-red-500 bg-red-50 rounded-lg">
          <h3 className="font-semibold mb-2">出现了一些问题</h3>
          <p className="text-sm text-red-600">{this.state.error?.message}</p>
          <button
            className="mt-2 px-4 py-2 text-sm bg-red-100 text-red-600 rounded hover:bg-red-200"
            onClick={() => window.location.reload()}
          >
            刷新页面
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

const StreamingOutput = () => {
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef(null);
  const [localError, setLocalError] = useState(null);
  const inputAreaRef = useRef(null);

  const {
    messages,
    isLoading,
    error,
    currentMessageId,
    currentConversationId,
    handleSend,
    createNewConversation,
    setMessages,
    setCurrentMessageId,
    handleInputChange,
    setCurrentConversationId,
  } = useChat();

  const {
    uploadedImages,
    uploadedFiles,
    handleImageUpload,
    handleFileUpload,
    handleDeleteImage,
    handleDeleteFile,
    clearUploads,
  } = useFileUpload();

  const {
    histories,
    isLoading: isHistoryLoading,
    error: historyError,
    updateHistory,
    fetchHistories,
  } = useChatHistory();

  useEffect(() => {
    if (error || historyError) {
      const errorMessage = error?.message || historyError?.message || '操作失败';
      setLocalError(errorMessage);
      const timer = setTimeout(() => setLocalError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error, historyError]);

  useEffect(() => {
    if (messagesEndRef.current) {
      const smoothScroll = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      };
      requestAnimationFrame(smoothScroll);
    }
  }, [messages]);

  const handleNewChat = async () => {
    try {
      const result = await createNewConversation();
      await clearUploads();
    } catch (error) {
      console.error('创建新对话失败:', error);
      setLocalError('创建新对话失败');
    }
  };

  const handleSelectHistory = async (history) => {
    try {
      await clearUploads();

      if (!history?.messages) {
        throw new Error('历史记录数据无效');
      }

      const newMessages = history.messages.map((msg, index) => {
        if (!msg?.query || !msg?.response) {
          console.warn('无效的消息记录:', msg);
          return null;
        }

        const userMessage = {
          id: `${history.message_id}_user_${index}`,
          type: 'user',
          content: msg.query,
          timestamp: new Date(msg.timestamp).toLocaleTimeString(),
          attachments: msg.attachments
        };

        const assistantMessage = {
          id: `${history.message_id}_assistant_${index}`,
          type: 'assistant',
          content: msg.response,
          timestamp: new Date(msg.timestamp).toLocaleTimeString(),
          thinkingProcess: '✓ 完成'
        };

        return [userMessage, assistantMessage];
      })
      .filter(Boolean)
      .flat();

      setCurrentConversationId(history.conversation_id);
      setCurrentMessageId(history.message_id);
      setMessages(newMessages);
      setShowHistory(false);

    } catch (error) {
      console.error('加载历史记录失败:', error);
      setLocalError('加载历史记录失败');
    }
  };

  const handleUpdateHistory = async (messageId, updates) => {
    if (!messageId || !updates) {
      console.warn('Invalid parameters for history update');
      return;
    }

    try {
      await updateHistory(messageId, updates);

      if (messageId === currentMessageId && updates.title) {
        setMessages(prev => {
          if (!prev.length) return prev;
          return [
            { ...prev[0], title: updates.title },
            ...prev.slice(1)
          ];
        });
      }

    } catch (error) {
      console.error('Failed to update history:', error);
      setLocalError('更新历史记录失败');
    }
  };

  const handleDeleteHistory = async (conversationId) => {
    if (!conversationId) {
      console.warn('Invalid conversationId for deletion');
      return;
    }

    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/chat/history/${conversationId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || '删除失败');
      }

      if (conversationId === currentConversationId) {
        setMessages([]);
        setCurrentConversationId(null);
        setCurrentMessageId(null);
      }

      await fetchHistories();

    } catch (error) {
      console.error('Failed to delete history:', error);
      setLocalError('删除历史记录失败');
    }
  };

  const handleSendMessage = async (formData) => {
    if (!formData) {
      setLocalError('请输入消息内容');
      return;
    }

    try {
      const currentImages = [...uploadedImages];
      const currentFiles = [...uploadedFiles];

      await clearUploads();

      await handleSend({
        ...formData,
        images: currentImages.map(img => img.file.serverPath),
        files: currentFiles.map(file => file.file.serverPath),
      });

    } catch (error) {
      console.error('Failed to send message:', error);
      setLocalError('发送消息失败');
    }
  };

  const toggleHistory = useCallback(() => {
    setShowHistory(prev => !prev);
  }, []);
  const [maxMemory, setMaxMemory] = useState(10);

  const quickTools = useMemo(() => [
    {
      icon: Clock,
      label: '历史记录',
      action: toggleHistory
    },
    {
      component: MemorySettings,
      props: {
        maxMemory,
        onChangeMemory: setMaxMemory,
        messagesLength: Math.floor(messages.length / 2)
      }
    }
  ], [toggleHistory, maxMemory, messages.length]);

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-[#f9fafb]">
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopNav
            createNewConversation={handleNewChat}
            currentMessageId={currentMessageId}
            currentConversationId={currentConversationId}
          />

          <div className="flex-1 overflow-y-auto">
            <ChatArea
              messages={messages}
              isLoading={isLoading}
              error={localError}
              messagesEndRef={messagesEndRef}
            />
          </div>

          <InputArea
            ref={inputAreaRef}
            onInputChange={handleInputChange}
            isLoading={isLoading}
            handleSend={handleSendMessage}
            uploadedImages={uploadedImages}
            uploadedFiles={uploadedFiles}
            handleImageUpload={handleImageUpload}
            handleFileUpload={handleFileUpload}
            handleDeleteImage={handleDeleteImage}
            handleDeleteFile={handleDeleteFile}
            quickTools={quickTools}
            conversationId={currentConversationId}
            maxMemory={maxMemory}
          />
        </div>

        {showHistory && (
          <HistoryList
            histories={histories}
            currentMessageId={currentMessageId}
            isLoading={isHistoryLoading}
            error={historyError}
            onSelectHistory={handleSelectHistory}
            onUpdateHistory={handleUpdateHistory}
            onDeleteHistory={handleDeleteHistory}
            onClose={() => setShowHistory(false)}
          />
        )}
      </div>
    </ErrorBoundary>
  );
};

export default StreamingOutput;