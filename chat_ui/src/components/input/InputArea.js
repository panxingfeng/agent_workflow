import React, { useRef, useState, useEffect } from 'react';
import { Send, Image, Paperclip, XCircle, Mic, MicOff, Plus } from 'lucide-react';
import { API_CONFIG } from "../../constants";
import RagUploadDialog from "./RagUploadDialog";

const InputArea = React.forwardRef(({
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
}, ref) => {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef(null);
  const [usedRags, setUsedRags] = useState(new Set());
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const mediaRecorderRef = useRef(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [recordingTime, setRecordingTime] = useState(0);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const [micPermission, setMicPermission] = useState('prompt');
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showVoiceConfirm, setShowVoiceConfirm] = useState(false);

  React.useImperativeHandle(ref, () => ({
    resetToInitial: () => {
      setInputValue('');
      if (inputRef.current) {
        inputRef.current.style.height = '44px';
        inputRef.current.style.overflowY = 'hidden';
        inputRef.current.placeholder = "请输入消息...";
      }

      setShowUploadMenu(false);
      setShowVoiceConfirm(false);
      setErrorMessage('');
      setRecordingTime(0);

      if (isRecording) {
        stopRecording();
      }

      if (quickTools?.length > 0) {
        quickTools.forEach(tool => {
          if (tool.reset) {
            tool.reset();
          }
        });
      }
    }
  }));

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

      await ref.current?.resetToInitial();

      await handleSend(messageData);

    } catch (error) {
      console.error('发送消息失败:', error);
      setErrorMessage('发送消息失败: ' + error.message);
    }
  };

  const checkAudioDevices = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        throw new Error('您的浏览器不支持音频设备访问');
      }

      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioDevices = devices.filter(device => device.kind === 'audioinput');

      if (audioDevices.length === 0) {
        throw new Error('未检测到麦克风设备，请确保麦克风已正确连接');
      }

      return true;
    } catch (error) {
      console.error('音频设备检查失败:', error);
      setErrorMessage(error.message);
      return false;
    }
  };

  const checkMicrophonePermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      stream.getTracks().forEach(track => track.stop());
      setMicPermission('granted');
      return true;
    } catch (error) {
      console.error('麦克风权限检查失败:', error);
      if (error.name === 'NotAllowedError') {
        setMicPermission('denied');
      }
      return false;
    }
  };

  useEffect(() => {
    checkMicrophonePermission();
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  useEffect(() => {
    if (inputValue) {
      requestAnimationFrame(adjustInputHeight);
    }
  }, [inputValue]);

  const handleLocalKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleLocalSend();
    }
    handleKeyPress?.(e);
  };

  const handleMicClick = async () => {
    if (isRecording) {
      stopRecording();
    } else if (micPermission === 'granted') {
      ref.current?.resetToInitial();
      startRecording();
    } else {
      const granted = await checkMicrophonePermission();
      if (granted) {
        ref.current?.resetToInitial();
        startRecording();
      } else {
        setErrorMessage('请在浏览器设置中允许访问麦克风');
      }
    }
  };

  const startRecording = async () => {
    try {
      setErrorMessage('');
      setRecordingTime(0);
      chunksRef.current = [];

      const hasAudioDevice = await checkAudioDevices();
      if (!hasAudioDevice) {
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      const mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        try {
          const audioBlob = new Blob(chunksRef.current);
          const arrayBuffer = await audioBlob.arrayBuffer();
          const audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000
          });
          const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
          const wavBuffer = createWavBuffer(audioBuffer);
          const wavBlob = new Blob([wavBuffer], { type: 'audio/wav' });
          const formData = new FormData();
          formData.append('audio_file', wavBlob, 'recording.wav');

          const response = await fetch(`${API_CONFIG.baseUrl}/speech-to-text`, {
            method: 'POST',
            body: formData
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '语音识别失败');
          }

          const data = await response.json();
          if (data.full_text) {
            setInputValue(prev => {
              const space = prev.length > 0 ? ' ' : '';
              const newValue = prev + space + data.full_text;
              requestAnimationFrame(() => {
                if (inputRef.current) {
                  adjustInputHeight();
                }
              });
              return newValue;
            });
          } else {
            setErrorMessage('未检测到语音内容');
          }

        } catch (error) {
          console.error('处理录音失败:', error);
          setErrorMessage('处理录音失败: ' + error.message);
        }

        if (mediaRecorder.stream) {
          mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000);
      setIsRecording(true);

      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

    } catch (error) {
      console.error('录音错误:', error);
      let errorMsg = '开始录音失败: ';

      switch (error.name) {
        case 'NotFoundError':
          errorMsg += '找不到麦克风设备，请确保设备已正确连接';
          break;
        case 'NotAllowedError':
          errorMsg += '麦克风访问被拒绝，请在浏览器设置中允许访问';
          setMicPermission('denied');  // 更新权限状态
          break;
        case 'NotReadableError':
          errorMsg += '麦克风被其他应用程序占用';
          break;
        default:
          errorMsg += error.message || '未知错误';
      }

      setErrorMessage(errorMsg);
      setIsRecording(false);
    }
  };

  function createWavBuffer(audioBuffer) {
    const numOfChannels = audioBuffer.numberOfChannels;
    const length = audioBuffer.length * numOfChannels * 2;
    const buffer = new ArrayBuffer(44 + length);
    const view = new DataView(buffer);
    const channels = [];
    let offset = 0;
    let pos = 0;

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numOfChannels, true);
    view.setUint32(24, audioBuffer.sampleRate, true);
    view.setUint32(28, audioBuffer.sampleRate * 2, true);
    view.setUint16(32, numOfChannels * 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, length, true);

    for (let i = 0; i < audioBuffer.numberOfChannels; i++) {
      channels.push(audioBuffer.getChannelData(i));
    }

    offset = 44;
    while (pos < audioBuffer.length) {
      for (let i = 0; i < numOfChannels; i++) {
        let sample = Math.max(-1, Math.min(1, channels[i][pos]));
        sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, sample, true);
        offset += 2;
      }
      pos++;
    }

    return buffer;
  }

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setShowVoiceConfirm(true);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const handleLocalInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);
    requestAnimationFrame(adjustInputHeight);
    onInputChange?.(e);
  };

  React.useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const handleLocalImageUpload = async (e) => {
    if (!e.target?.files?.length) return;

    try {
      const files = Array.from(e.target.files);
      const allowedImageTypes = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
      ];

      const validImageFiles = files.filter(file => allowedImageTypes.includes(file.type));

      if (validImageFiles.length === 0) {
        throw new Error('只允许上传图片格式的文件（JPEG、PNG、GIF、WebP）');
      }

      const formData = new FormData();

      validImageFiles.forEach(file => {
        formData.append('images', file);
      });

      const response = await fetch(`${API_CONFIG.baseUrl}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('上传失败');

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
      console.error('图片上传失败:', error.message);
    }
  };

  const handleLocalFileUpload = async (e) => {
    if (!e.target?.files?.length) return;

    try {
      const files = Array.from(e.target.files);
      const allowedTypes = [
        'application/pdf',
        'text/plain',
        'text/markdown',
        'application/msword',
      ];
      const allowedExtensions = ['.pdf', '.md', '.txt', '.doc'];

      const validFiles = files.filter(file => {
        const fileExtension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
        return allowedTypes.includes(file.type) || allowedExtensions.includes(fileExtension);
      });

      if (validFiles.length === 0) {
        alert('只允许上传 PDF、MD、TXT 和 DOC 文件');
        return
      }

      const formData = new FormData();

      validFiles.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch(`${API_CONFIG.baseUrl}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('上传失败');

      const result = await response.json();

      if (result.files && result.files.length > 0) {
        const fileList = validFiles.map((originalFile, index) => {
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
      console.error('文件上传失败:', error.message);
      alert(`文件上传失败: ${error.message}`);
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

  const adjustInputHeight = () => {
    const input = inputRef.current;
    if (!input) return;

    input.style.height = 'auto';
    input.style.overflowY = 'hidden';

    const scrollHeight = input.scrollHeight;

    if (!input.value.trim()) {
      input.style.height = '44px';
      input.style.overflowY = 'hidden';
      return;
    }

    const newHeight = Math.min(150, Math.max(44, scrollHeight));
    input.style.height = `${newHeight}px`;

    if (scrollHeight > 150) {
      input.style.overflowY = 'auto';
      requestAnimationFrame(() => {
        input.scrollTop = input.scrollHeight;
      });
    }
  };

  const isDisabled = isLoading ||
    (!inputValue.trim() && !uploadedImages?.length && !uploadedFiles?.length && !usedRags.size);

  return (
    <div className="w-full max-w-4xl mx-auto p-4">
      <div className="p-2 flex flex-col space-y-2 rounded-xl" style={{backgroundColor: 'transparent'}}>
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
                        {tool.icon && <tool.icon size={14}/>}
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
                      <XCircle size={14}/>
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
                      <Paperclip size={14} className="text-gray-500 mr-1 flex-shrink-0"/>
                      <span className="text-sm text-gray-700 truncate">{file.name}</span>
                    </a>
                    <button
                        onClick={() => handleLocalDeleteFile(index)}
                        className="ml-1 p-1 hover:bg-gray-200 rounded-full flex-shrink-0"
                    >
                      <XCircle size={14} className="text-gray-500"/>
                    </button>
                  </div>
              ))}
            </div>
        )}

        {/* 输入区域 */}
        <div className="flex flex-col space-y-2">
          <div className="flex items-center space-x-2 bg-white rounded-lg p-2">
            <button
                onClick={() => setShowUploadMenu(!showUploadMenu)}
                className="p-2 hover:bg-gray-100 rounded-lg flex-shrink-0"
            >
              <Plus
                  size={20}
                  className={`text-gray-500 transform transition-transform ${showUploadMenu ? 'rotate-45' : ''}`}
              />
            </button>

            <button
                onClick={handleMicClick}
                className={`p-2 hover:bg-gray-100 rounded-lg flex-shrink-0 ${isRecording ? 'bg-red-100' : ''}`}
            >
              {isRecording ? (
                  <MicOff size={20} className="text-red-500"/>
              ) : (
                  <Mic size={20} className="text-gray-500"/>
              )}
            </button>

            <textarea
                ref={inputRef}
                className="flex-1 resize-none outline-none p-2"
                rows="1"
                value={inputValue}
                onChange={handleLocalInputChange}
                onKeyPress={handleLocalKeyPress}
                placeholder={isRecording ? "正在录音..." : "请输入消息..."}
                disabled={isLoading}
                style={{
                  minHeight: '44px',
                  maxHeight: '150px',
                  transition: 'height 0.2s ease',
                  overflowY: 'hidden'
                }}
            />

            <button
                onClick={handleLocalSend}
                disabled={isDisabled}
                className="p-2 hover:bg-gray-100 rounded-lg flex-shrink-0 disabled:opacity-50"
            >
              <Send size={20} className={isDisabled ? 'text-gray-300' : 'text-gray-500'}/>
            </button>
          </div>

          {/* 上传菜单 */}
          {showUploadMenu && (
              <div className="flex space-x-2 p-2 bg-white rounded-lg">
                <label className="flex items-center space-x-2 p-2 hover:bg-gray-100 rounded-lg cursor-pointer">
                  <Image size={20} className="text-gray-500"/>
                  <span className="text-sm text-gray-700">图片</span>
                  <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleLocalImageUpload}
                      multiple
                      disabled={uploadedImages?.length >= 5}
                  />
                </label>
                <label className="flex items-center space-x-2 p-2 hover:bg-gray-100 rounded-lg cursor-pointer">
                  <Paperclip size={20} className="text-gray-500"/>
                  <span className="text-sm text-gray-700">文件</span>
                  <input
                      type="file"
                      className="hidden"
                      onChange={handleLocalFileUpload}
                      multiple
                      disabled={uploadedFiles?.length >= 5}
                  />
                </label>
              </div>
          )}

          {/* 语音确认框 */}
          {showVoiceConfirm && (
              <div className="flex justify-end space-x-2 p-2 bg-white rounded-lg">
                <button
                    onClick={() => {
                      setShowVoiceConfirm(false);
                      setInputValue('');
                    }}
                    className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  取消
                </button>
                <button
                    onClick={handleLocalSend}
                    className="px-4 py-2 text-sm text-white bg-blue-500 hover:bg-blue-600 rounded-lg"
                >
                  发送
                </button>
              </div>
          )}

          {/* 错误提示 */}
          {errorMessage && (
            <div className="text-red-500 text-sm px-2">
              {errorMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default React.memo(InputArea);