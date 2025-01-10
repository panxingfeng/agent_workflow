import { useState, useEffect, useMemo } from 'react';
import { Search, XCircle } from 'lucide-react';
import { useChatHistory } from '../../hooks/useChatHistory';
import { HistoryItem } from './HistoryItem';

export const HistoryList = ({
  currentConversationId,
  onSelectHistory,
  onClose
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const {
    histories,
    isLoading,
    error,
    fetchHistories,
    deleteHistory,
    updateHistory
  } = useChatHistory();

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      fetchHistories({ search: searchQuery }).then(r => { });
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchQuery, fetchHistories]);

  const handleDeleteHistory = async (conversationId) => {
    try {
      await deleteHistory(conversationId);
      await fetchHistories();
    } catch (error) {
      console.error('Failed to delete history:', error);
    }
  };

  const handleUpdateHistory = async (conversationId, updates) => {
    try {
      await updateHistory(conversationId, updates);
      await fetchHistories();
    } catch (error) {
      console.error('Failed to update history:', error);
    }
  };

  const sortedHistories = useMemo(() => {
    const historyArray = Array.isArray(histories) ? histories : [];
    return [...historyArray].sort((a, b) => {
      if (a.pinned !== b.pinned) return b.pinned ? 1 : -1;
      if (a.starred !== b.starred) return b.starred ? 1 : -1;
      return new Date(b.timestamp) - new Date(a.timestamp);
    });
  }, [histories]);

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white shadow-xl flex flex-col z-50">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">历史记录</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <XCircle size={20} className="text-gray-500" />
          </button>
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="搜索历史记录..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-100 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-500">
            {error}
          </div>
        ) : sortedHistories.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {searchQuery ? '无搜索结果' : '暂无历史记录'}
          </div>
        ) : (
          <div className="space-y-2">
            {sortedHistories.map((history) => (
              <HistoryItem
                key={history.conversation_id}
                conversation={history}
                isActive={history.conversation_id === currentConversationId}
                onSelect={() => onSelectHistory(history)}
                onDelete={() => handleDeleteHistory(history.conversation_id)}
                onUpdate={(updates) => handleUpdateHistory(history.conversation_id, updates)}
              />
            ))}
          </div>
        )}
      </div>

      {searchQuery && (
        <div className="p-4 border-t border-gray-200">
          <button
            onClick={() => setSearchQuery('')}
            className="w-full py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm transition-colors"
          >
            清除搜索
          </button>
        </div>
      )}
    </div>
  );
};