import React, { useRef, useState } from 'react';
import { Send, Image, Paperclip, XCircle } from 'lucide-react';
import { API_CONFIG } from "../../constants";
import RagUploadDialog from "./RagUploadDialog";

const InputArea = ({
  onInputChange,
  isLoading,
  handleSend,
  handleKeyPress,
  uploadedImages = [],
  uploadedFiles = [],
  handleImageUpload,
  handleFileUpload,
  handleDeleteImage,
  handleDeleteFile,
  quickTools,
  maxMemory,
  onRagFilesUpload,
}) => {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef(null);
  const inputHeightRef = useRef(null);
  const [usedRags, setUsedRags] = useState(new Set());

  const handleLocalInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      const newHeight = Math.min(150, Math.max(44, inputRef.current.scrollHeight));
      if (newHeight !== inputHeightRef.current) {
        inputHeightRef.current = newHeight;
        inputRef.current.style.height = `${newHeight}px`;
      }
    }
    onInputChange?.(e);
  };

  const handleLocalImageUpload = async (e) => {
    if (!e.target?.files?.length) return;

    try {
      const files = Array.from(e.target.files);
      const formData = new FormData();

      files.forEach(file => {
        formData.append('images', file);
      });

      const response = await fetch(`${API_CONFIG.baseUrl}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('Upload failed');

      const result = await response.json();

      if (result.files && result.files.length > 0) {
        const fileList = result.files.map((serverFile) => ({
          file: {
            name: serverFile.name,
            serverPath: serverFile.path,
            serverUrl: serverFile.url
          },
          name: serverFile.name,
          previewUrl: serverFile.url
        }));

        await handleImageUpload({
          target: {
            files: fileList
          }
        });
      }

    } catch (error) {
      console.error('图片上传失败:', error);
    }
  };

  const handleLocalFileUpload = async (e) => {
    if (!e.target?.files?.length) return;

    try {
      const files = Array.from(e.target.files);
      const formData = new FormData();

      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch(`${API_CONFIG.baseUrl}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('Upload failed');

      const result = await response.json();

      if (result.files && result.files.length > 0) {
        const fileList = files.map((originalFile, index) => {
          const serverFile = result.files[index];
          originalFile.serverUrl = serverFile.url;
          originalFile.serverPath = serverFile.path;
          return originalFile;
        });

        await handleFileUpload({
          target: {
            files: fileList
          }
        });
      }

    } catch (error) {
      console.error('文件上传失败:', error);
    }
  };

  const handleLocalDeleteImage = async (index) => {
    try {
      const image = uploadedImages[index];
      if (image?.file?.serverPath) {
        await fetch(`${API_CONFIG.baseUrl}/delete?path=${encodeURIComponent(image.file.serverPath)}`, {
          method: 'DELETE'
        });
      }
      handleDeleteImage?.(index);
    } catch (error) {
      console.error('图片删除失败:', error);
    }
  };

  const handleLocalDeleteFile = async (index) => {
    try {
      const file = uploadedFiles[index];
      if (file?.file?.serverPath) {
        await fetch(`${API_CONFIG.baseUrl}/delete?path=${encodeURIComponent(file.file.serverPath)}`, {
          method: 'DELETE'
        });
      }
      handleDeleteFile?.(index);
    } catch (error) {
      console.error('文件删除失败:', error);
    }
  };

  const handleLocalSend = async () => {
    try {
      const text = inputValue.trim();
      if (!text && uploadedImages.length === 0 && uploadedFiles.length === 0 && usedRags.size === 0) {
        return;
      }

      const messageData = {
        message_id: Date.now().toString(),
        query: text,
        context_length: maxMemory,
        images: uploadedImages.map(img => img.file.serverPath),
        files: uploadedFiles.map(file => file.file.serverPath),
        rags: Array.from(usedRags)
      };

      await handleSend(messageData);
      setInputValue('');
      inputRef.current?.focus();

    } catch (error) {
      console.error('发送消息失败:', error);
    }
  };

  const handleLocalKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleLocalSend().then(r => { });
    }
    handleKeyPress?.(e);
  };

  const handleRagUse = (ragName) => {
    if (ragName === null) {
      setUsedRags(new Set());
    } else {
      setUsedRags(prev => {
        const newSet = new Set(prev);
        if (newSet.has(ragName)) {
          newSet.delete(ragName);
        } else {
          newSet.add(ragName);
        }
        return newSet;
      });
    }
  };

  const isDisabled = isLoading ||
    (!inputValue.trim() && !uploadedImages?.length && !uploadedFiles?.length && !usedRags.size);

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <div className="p-2 flex flex-col space-y-2 rounded-xl" style={{ backgroundColor: 'transparent' }}>
        {quickTools?.length > 0 && (
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center space-x-2">
              {quickTools.map((tool, index) => {
                if (tool.component) {
                  const ToolComponent = tool.component;
                  return <ToolComponent key={index} {...tool.props} />;
                }
                return (
                  <button
                    key={index}
                    onClick={tool.action}
                    className="text-gray-500 hover:text-gray-800 text-sm flex items-center space-x-1"
                  >
                    {tool.icon && <tool.icon size={14} />}
                    <span>{tool.label}</span>
                  </button>
                );
              })}
            </div>

            <RagUploadDialog
              onFilesUploaded={onRagFilesUpload}
              onRagUse={handleRagUse}
            />
          </div>
        )}

        {/* 图片预览区 */}
        {Array.isArray(uploadedImages) && uploadedImages.length > 0 && (
          <div className="flex space-x-2 overflow-x-auto mb-2 p-2">
            {uploadedImages.map((image, index) => (
              <div key={index} className="relative group">
                <div className="w-16 h-16 rounded-lg overflow-hidden border border-gray-200">
                  <img
                    src={image.previewUrl}
                    alt={`预览图 ${index + 1}`}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      console.error('预览图加载失败:', image);
                      e.target.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="%23eee"/></svg>';
                    }}
                  />
                </div>
                <button
                  onClick={() => handleLocalDeleteImage(index)}
                  className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full
                           flex items-center justify-center opacity-0 group-hover:opacity-100
                           transition-opacity shadow-lg"
                >
                  <XCircle size={14} />
                </button>
              </div>
            ))}
            <div className="flex items-center text-sm text-gray-500">
              {uploadedImages.length}/5
            </div>
          </div>
        )}

        {/* 文件预览区 */}
        {Array.isArray(uploadedFiles) && uploadedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 p-2">
            {uploadedFiles.map((file, index) => (
              <div key={index} className="flex items-center bg-gray-100 rounded-lg px-2 py-1 max-w-[200px]">
                <a
                  href={file.previewUrl || file.serverUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center hover:text-blue-500 truncate"
                >
                  <Paperclip size={14} className="text-gray-500 mr-1 flex-shrink-0" />
                  <span className="text-sm text-gray-700 truncate">{file.name}</span>
                </a>
                <button
                  onClick={() => handleLocalDeleteFile(index)}
                  className="ml-1 p-1 hover:bg-gray-200 rounded-full flex-shrink-0"
                >
                  <XCircle size={14} className="text-gray-500" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 输入区域 */}
        <div className="p-2 flex items-center space-x-2 bg-transparent">
          <div className="flex items-center space-x-1">
            <label className="p-2 hover:bg-gray-200 rounded-lg cursor-pointer relative">
              <Image size={20} className="text-gray-500" />
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleLocalImageUpload}
                multiple
                disabled={uploadedImages?.length >= 5}
              />
              {uploadedImages?.length >= 5 && (
                <div className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </label>

            <label className="p-2 hover:bg-gray-200 rounded-lg cursor-pointer relative">
              <Paperclip size={20} className="text-gray-500" />
              <input
                type="file"
                className="hidden"
                onChange={handleLocalFileUpload}
                multiple
                disabled={uploadedFiles?.length >= 5}
              />
              {uploadedFiles?.length >= 5 && (
                <div className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </label>
          </div>

          <textarea
            ref={inputRef}
            className="flex-1 resize-none outline-none bg-white rounded-lg p-2 h-full overflow-y-auto"
            rows="1"
            value={inputValue}
            onChange={handleLocalInputChange}
            onKeyPress={handleLocalKeyPress}
            placeholder="请输入消息..."
            disabled={isLoading}
            style={{
              minHeight: '44px',
              maxHeight: '150px'
            }}
          />

          <button
            onClick={handleLocalSend}
            disabled={isDisabled}
            className="p-2 hover:bg-gray-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send
              size={20}
              className={`${isDisabled ? 'text-gray-300' : 'text-gray-500'}`}
            />
          </button>
        </div>
      </div>
    </div>
  );
};

export default React.memo(InputArea);