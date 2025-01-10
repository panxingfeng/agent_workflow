import React from 'react';
import { Brain, Paperclip } from 'lucide-react';
import MessageContent from './detail/MessageContent';
import { ASSISTANT_TITLE, ASSISTANT_DESCRIPTION } from '../../constants';

const ChatArea = ({ messages, error, messagesEndRef }) => {
    if (!messages || messages.length === 0) {
        return (
            <div className="text-center py-12">
                <h2 className="text-2xl font-bold text-gray-800 mb-3">{ASSISTANT_TITLE}</h2>
                <p className="text-gray-500 mb-8">{ASSISTANT_DESCRIPTION}</p>
            </div>
        );
    }

    return (
        <div className="w-full mx-auto p-6 space-y-6">
            {messages.map((message, index) => {
                const isUser = message.type === 'user';

                return (
                    <div
                        key={`message-${index}`}
                        className={`flex items-start ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                    >
                        {!isUser && (
                            <div
                                className="flex-shrink-0 w-8 h-8 rounded-lg mr-4 bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                                <Brain className="w-5 h-5 text-white" />
                            </div>
                        )}

                        <div
                            className={`relative flex ${isUser ? 'justify-end ml-4' : 'mr-4'} max-w-[85%] sm:max-w-[75%] md:max-w-[65%] lg:max-w-[55%]`}>
                            <div className={`inline-block rounded-2xl shadow-sm ${isUser
                                ? 'bg-blue-500 text-white rounded-tr-sm'
                                : 'bg-white border border-gray-200 rounded-tl-sm'
                                }`}>
                                <div className="p-4">
                                    {isUser ? (
                                        <div className="space-y-2">
                                            <div className="whitespace-pre-wrap break-words">
                                                {typeof message.content === 'string'
                                                    ? message.content
                                                    : message.content?.text || message.query || ''
                                                }
                                            </div>

                                            {/* 附件预览 */}
                                            {message.attachments && (
                                                <div className="mt-2 space-y-2">
                                                    {/* 图片预览 */}
                                                    {message.attachments?.images?.length > 0 && (
                                                        <div className="flex flex-wrap gap-2">
                                                            {message.attachments.images.map((image, imgIndex) => (
                                                                <div key={imgIndex} className="relative">
                                                                    <img
                                                                        src={image.saved_path || image.preview || image.url}
                                                                        alt={image.original_name || `Preview ${imgIndex + 1}`}
                                                                        className="max-w-[150px] h-auto rounded-lg"
                                                                        onError={(e) => {
                                                                            console.error('Image load failed:', image);
                                                                            e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="150" height="150"><rect width="150" height="150" fill="%23eee"/></svg>';
                                                                        }}
                                                                    />
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}

                                                    {/* 文件预览 */}
                                                    {message.attachments.files?.length > 0 && (
                                                        <div className="space-y-2">
                                                            {message.attachments.files.map((file, fileIndex) => (
                                                                <div key={fileIndex}
                                                                    className="flex items-center gap-2 p-2 bg-white bg-opacity-10 rounded-lg">
                                                                    <Paperclip className="text-white" size={16} />
                                                                    <a
                                                                        href={file.saved_path}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="text-sm text-white underline"
                                                                    >
                                                                        {file.original_name || file.name || 'File'}
                                                                    </a>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}

                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div className="max-w-none">
                                            <MessageContent
                                                messageId={message.id}
                                                content={message.content}
                                                type={message.type}
                                                thinkingProcess={message.thinkingProcess}
                                            />
                                        </div>
                                    )}
                                </div>

                                <div className={`text-xs px-4 pb-2 ${isUser ? 'text-blue-100' : 'text-gray-400'}`}>
                                    {message.timestamp}
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })}

            {error && (
                <div className="bg-red-50 text-red-500 p-4 rounded-lg text-center">
                    {error}
                </div>
            )}

            <div ref={messagesEndRef} />
        </div>
    );
};

export default ChatArea;