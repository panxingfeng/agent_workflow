import { Pin, Star, MessageSquare, Trash2 } from 'lucide-react';

export const HistoryItem = ({
  conversation,
  isActive,
  onSelect,
  onDelete,
}) => {
  const renderLatestMessage = () => {
    if (!conversation.messages?.length) return '';

    const latestMessage = conversation.messages[conversation.messages.length - 1];
    return latestMessage.query.length > 50
      ? `${latestMessage.query.slice(0, 50)}...`
      : latestMessage.query;
  };

  const handleDeleteClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (window.confirm('确定要删除这个对话吗？')) {
      await onDelete();
    }
  };

  return (
    <>
      <div
        onClick={onSelect}
        className={`group relative p-3 rounded-lg cursor-pointer transition-colors
          ${isActive ? 'bg-blue-50' : 'hover:bg-gray-100'}`}
      >

        <div className="pr-8">
          <div className="flex items-center gap-2">
            <h4 className="font-medium truncate">
              {conversation.title || '新对话'}
            </h4>
            {conversation.starred && (
              <Star size={14} className="text-yellow-500 flex-shrink-0" />
            )}
            {conversation.pinned && (
              <Pin size={14} className="text-blue-500 flex-shrink-0" />
            )}
          </div>

          <p className="text-sm text-gray-600 truncate mt-1">
            {renderLatestMessage()}
          </p>

          <p className="text-xs text-gray-500 mt-1">
            {new Date(conversation.timestamp).toLocaleString()}
          </p>
        </div>

        <div className="absolute right-2 top-1/2 -translate-y-1/2 space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
            }}
            className="p-1 hover:bg-gray-200 rounded-full"
            title="查看对话详情"
          >
            <MessageSquare size={14} className="text-gray-600" />
          </button>
          <button
            onClick={handleDeleteClick}
            className="p-1 hover:bg-gray-200 rounded-full"
            title="删除对话"
          >
            <Trash2 size={14} className="text-red-500" />
          </button>
        </div>
      </div>
    </>
  );
};