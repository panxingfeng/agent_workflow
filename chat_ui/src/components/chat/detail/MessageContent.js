import React, {useEffect, useMemo, useRef, useState} from 'react';
import {ChevronDown, ChevronUp, Download, Paperclip, Pause, Play, RotateCcw} from 'lucide-react';
import {LOADING_TEXT} from "../../../constants";

// 音频播放器组件
const AudioPlayer = ({ url }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);
  const progressInterval = useRef(null);

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '00:00';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const updateProgress = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handlePlayPause = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      clearInterval(progressInterval.current);
    } else {
      audioRef.current.play();
      progressInterval.current = setInterval(updateProgress, 100);
    }
    setIsPlaying(!isPlaying);
  };

  const handleRestart = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    setCurrentTime(0);
    audioRef.current.play();
    setIsPlaying(true);
    progressInterval.current = setInterval(updateProgress, 100);
  };

  useEffect(() => {
    return () => {
      if (progressInterval.current) {
        clearInterval(progressInterval.current);
      }
    };
  }, []);

  const progressPercentage = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-3 p-3 bg-gray-100 rounded-lg max-w-[320px]">
        <button
          onClick={handlePlayPause}
          className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${isPlaying ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-500'
            }`}
        >
          {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-1" />}
        </button>

        <div className="flex-1">
          <div
            className="h-1.5 bg-gray-200 rounded cursor-pointer relative"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const percentage = x / rect.width;
              const newTime = percentage * duration;
              audioRef.current.currentTime = newTime;
              setCurrentTime(newTime);
            }}
          >
            <div
              className="h-full bg-blue-500 rounded transition-all duration-200"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>

          <div className="flex justify-between items-center mt-2 px-1">
            <div className="font-mono text-xs text-gray-500 tabular-nums min-w-[45px]">
              {formatTime(currentTime)}
            </div>
            <div className="font-mono text-xs text-gray-500 tabular-nums min-w-[45px] text-right">
              {formatTime(duration)}
            </div>
          </div>
        </div>

        <button
          onClick={handleRestart}
          className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-gray-200 text-gray-500"
        >
          <RotateCcw size={16} />
        </button>

        <audio
          ref={audioRef}
          src={url}
          onEnded={() => {
            setIsPlaying(false);
            setCurrentTime(duration);
            clearInterval(progressInterval.current);
          }}
          onLoadedMetadata={() => {
            if (audioRef.current) {
              setDuration(audioRef.current.duration);
            }
          }}
          className="hidden"
        />
      </div>
    </div>
  );
};

// 图片组件
const ImageContent = ({ url, index }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const handleLoad = () => {
    setIsLoading(false);
  };

  const handleError = () => {
    console.error('图像加载失败:', url);
    setError(true);
    setIsLoading(false);
  };

  return (
    <>
      {/* 主图片容器 */}
      <div className="relative group w-full cursor-pointer" onClick={() => setShowModal(true)}>
        {/* Loading State */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
            <div className="text-sm text-gray-500">加载中...</div>
          </div>
        )}

        <img
          src={url}
          alt={`Generated Image ${index + 1}`}
          className={`w-full h-auto rounded-lg object-cover transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'
            }`}
          onLoad={handleLoad}
          onError={handleError}
        />

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-red-50 rounded-lg">
            <div className="text-red-500 text-sm">图片加载失败</div>
          </div>
        )}

        {!error && !isLoading && (
          <div className="absolute inset-0 bg-black bg-opacity-30 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center">
            <div className="text-white text-sm">点击查看大图</div>
          </div>
        )}
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75"
          onClick={() => setShowModal(false)}
        >
          <div className="relative w-full h-full md:w-4/5 md:h-4/5 flex items-center justify-center">
            <img
              src={url}
              alt={`Generated Image ${index + 1} (Full Size)`}
              className="max-w-full max-h-full rounded-lg object-contain"
              onClick={e => e.stopPropagation()}
            />
            <button
              className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full bg-black bg-opacity-50 text-white hover:bg-opacity-75 focus:outline-none"
              onClick={() => setShowModal(false)}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </>
  );
};

// 思考过程组件
const ThinkingProcess = React.memo(({ messageId, steps = [], isExpanded, onToggle }) => {
  const [displayedSteps, setDisplayedSteps] = useState(new Set());
  const [processedSteps, setProcessedSteps] = useState([]);

  useEffect(() => {
    const newProcessedSteps = steps.map((step, index) => {
      const isDebug = step.includes('[Debug]');
      const isSuccess = step.includes('✓') || step.includes('完成');
      const isError = step.includes('error') || step.includes('失败');
      const isNewStep = !displayedSteps.has(step);

      if (isNewStep) {
        setDisplayedSteps(prev => {
          const next = new Set(prev);
          next.add(step);
          return next;
        });
      }

      return {
        text: step,
        isDebug,
        isSuccess,
        isError,
        isNewStep,
        index
      };
    });

    setProcessedSteps(newProcessedSteps);
  }, [steps, messageId]);

  const isLoading = React.useMemo(() => {
    if (steps.length === 0) return true;
    const lastStep = steps[steps.length - 1];
    return !(lastStep.includes('✓') || lastStep.includes('完成') || lastStep.includes('error') || lastStep.includes('失败'));
  }, [steps]);

  return (
    <div className="mt-2">
      <button
        onClick={onToggle}
        className="inline-flex items-center space-x-2 text-sm text-gray-500 hover:text-gray-700 transition-colors px-3 py-1.5 rounded-md hover:bg-gray-50"
      >
        {isExpanded ? (
          <ChevronUp size={16} className="text-gray-400 group-hover:text-gray-600 transition-colors flex-shrink-0" />
        ) : (
          <ChevronDown size={16}
            className="text-gray-400 group-hover:text-gray-600 transition-colors flex-shrink-0" />
        )}
        <div className="font-medium">
          {isLoading ? (
              <span className="flex items-center whitespace-nowrap">
                {LOADING_TEXT}
                <span className="ml-1 animate-bounce">🤔</span>
              </span>
          ) : (
              <span className="text-gray-600 group-hover:text-gray-800 transition-colors">
              思考过程
            </span>
          )}
        </div>
      </button>

      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
        }`}>
        <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-100 shadow-sm">
          {processedSteps.map(({ text, isDebug, isSuccess, isError, isNewStep, index }) => (
            <div
              key={`${messageId}-${text}-${index}`}
              className={`flex items-start space-x-2.5 mb-2 last:mb-0 ${isNewStep ? 'animate-fade-in' : ''
                } ${isDebug ? 'text-blue-600' :
                  isSuccess ? 'text-green-600' :
                    isError ? 'text-red-600' :
                      'text-gray-600'
                }`}
              style={isNewStep ? {
                animationDelay: `${index * 50}ms`,
                animationFillMode: 'forwards'
              } : undefined}
            >
              <div className="pt-1.5 flex-shrink-0">
                <div className={`w-1.5 h-1.5 rounded-full ${isDebug ? 'bg-blue-500' :
                  isSuccess ? 'bg-green-500' :
                    isError ? 'bg-red-500' :
                      'bg-gray-400'
                  }`} />
              </div>
              <div className="text-sm break-words flex-1">
                {text}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

ThinkingProcess.displayName = 'ThinkingProcess';

// 链接预览卡片组件
const LinkPreview = ({ number, url }) => {
  const getFaviconUrl = (url) => {
    try {
      const domain = new URL(url).hostname;
      // 使用 Google Favicon Service 获取网站图标
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
    } catch {
      return null;
    }
  };

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center space-x-3 p-3 bg-white rounded-lg border border-gray-100 hover:bg-gray-50 transition-all duration-200"
    >
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
        <span className="text-sm text-gray-500">{number}</span>
      </div>

      <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
        <img
          src={getFaviconUrl(url)}
          alt=""
          className="w-4 h-4"
          onError={(e) => {
            e.target.style.display = 'none';
          }}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-500 truncate">
          {url}
        </div>
      </div>
    </a>
  );
};

// 链接预览列表组件
const LinkPreviewList = React.memo(({ links = [] }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [processedLinks, setProcessedLinks] = useState([]);

  useEffect(() => {
    if (Array.isArray(links) && links.length > 0) {
      setProcessedLinks(links);
    }
  }, [links]);

  if (!processedLinks?.length) return null;

  return (
    <div className="mt-4 max-w-[600px]">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center space-x-2 text-sm text-gray-500 hover:text-gray-700 transition-colors px-3 py-1.5 rounded-md hover:bg-gray-50"
      >
        {isExpanded ? (
          <ChevronUp size={16} className="text-gray-400 group-hover:text-gray-600 transition-colors flex-shrink-0" />
        ) : (
          <ChevronDown size={16} className="text-gray-400 group-hover:text-gray-600 transition-colors flex-shrink-0" />
        )}
        <div className="font-medium">
          <span className="text-gray-600 group-hover:text-gray-800 transition-colors">
            相关链接 ({processedLinks.length})
          </span>
        </div>
      </button>

      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${
        isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
      }`}>
        <div className="mt-2 space-y-2">
          {processedLinks.map((link) => (
            <LinkPreview
              key={`${link.url}-${link.number}`}  // 更好的 key
              number={link.number}
              url={link.url}
            />
          ))}
        </div>
      </div>
    </div>
  );
});

const style = document.createElement('style');
style.textContent = `
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fadeIn 0.5s ease-out;
}
`;
document.head.appendChild(style);

// 主消息内容组件
const MessageContent = ({ messageId, content, type = 'text', thinkingProcess }) => {
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  const [currentSteps, setCurrentSteps] = useState([]);
  const messageStatesRef = useRef(new Map());

  const isDialogMessage = (content) => {
    return content?.query !== undefined && content?.response !== undefined;
  };

  const extractLinks = (text) => {
    if (!text) {
      return [];
    }

    const links = [];
    const processedUrls = new Set();
    const processedRefs = new Set();

    const referenceMatches = text.matchAll(/\[(\d+)\]/g);
    for (const match of referenceMatches) {
      const number = parseInt(match[1], 10);
      if (number && !processedRefs.has(number)) {
        links.push({
          number,
          type: 'reference',
          title: `参考来源 ${number}`,
          isPlaceholder: true
        });
        processedRefs.add(number);
      }
    }

    const lines = text.split('\n');
    const urlList = [];
    let inLinkSection = false;
    lines.forEach((line, index) => {
      const linkMatch = line.match(/^(\d+)\.\s*(https?:\/\/[^\s]+)/);
      if (linkMatch) {
        inLinkSection = true;
        urlList.push({
          lineNumber: index + 1,
          number: parseInt(linkMatch[1], 10),
          url: linkMatch[2].trim()
        });
      }
    });

    links.forEach(link => {
      if (link.isPlaceholder) {
        const matchedUrl = urlList.find(url => url.number === link.number);
        if (matchedUrl) {
          link.url = matchedUrl.url;
          delete link.isPlaceholder;
          processedUrls.add(matchedUrl.url);
        }
      }
    });

    urlList.forEach(item => {
      if (!processedUrls.has(item.url)) {
        links.push({
          number: item.number,
          url: item.url,
          title: `参考来源 ${item.number}`,
          type: 'reference'
        });
        processedUrls.add(item.url);
      }
    });

    const validLinks = links.filter(link => !link.isPlaceholder);

    validLinks.sort((a, b) => a.number - b.number);

    return validLinks;
  };

  const cleanContent = (text) => {
    if (!text) return '';

    const lines = text.split('\n');
    let processedLines = [];
    let inLinkSection = false;

    for (const line of lines) {
      if (/^\d+\.\s*https?:\/\//.test(line)) {
        inLinkSection = true;
        continue;
      }

      if (!inLinkSection || !line.trim()) {
        processedLines.push(line);
      }
    }

    while (processedLines.length > 0 && !processedLines[processedLines.length - 1].trim()) {
      processedLines.pop();
    }

    return processedLines.join('\n');
  };
  const processMessageContent = (content) => {
    let normalizedContent = content;

    if (isDialogMessage(content)) {
      normalizedContent = content.response;
    }

    let result;
    if (normalizedContent?.type === 'mixed' ||
        (typeof normalizedContent === 'object' && normalizedContent?.text)) {

      const allImages = [
        ...(normalizedContent.images || []).map(img => ({
          url: img.url,
          previewUrl: img.url
        })),
        ...(normalizedContent.files || [])
          .filter(file => file.type === 'image')
          .map(file => ({
            url: file.url,
            previewUrl: file.url
          }))
      ];

      const otherFiles = (normalizedContent.files || [])
        .filter(file => file.type !== 'image')
        .map(file => ({
          url: file.url,
          name: file.name || file.filename || '',
          size: file.size || 0,
          type: file.type || ''
        }));

      result = {
        text: normalizedContent.text || '',
        links: extractLinks(normalizedContent.text || ''),
        images: allImages,
        files: otherFiles
      };

    } else if (normalizedContent?.files) {
      const images = normalizedContent.files
        .filter(file => file.type === 'image')
        .map(file => ({
          url: file.url,
          previewUrl: file.url
        }));

      const otherFiles = normalizedContent.files
        .filter(file => file.type !== 'image')
        .map(file => ({
          url: file.url,
          name: file.name || file.filename || '',
          size: file.size || 0,
          type: file.type || ''
        }));

      result = {
        text: normalizedContent.text || '',
        links: [],
        images,
        files: otherFiles
      };

    } else {
      const textContent = typeof normalizedContent === 'string'
        ? normalizedContent
        : normalizedContent?.text || '';

      result = {
        text: textContent,
        links: extractLinks(textContent),
        images: [],
        files: []
      };
    }

    return result;
  };

  const { text, links, images, files } = useMemo(() => {
    const processedContent = processMessageContent(content);
    return {
      text: cleanContent(processedContent.text),
      links: processedContent.links,
      images: processedContent.images,
      files: processedContent.files
    };
  }, [content]);

  // 处理思考过程
  useEffect(() => {
    if (thinkingProcess) {
      const newSteps = thinkingProcess.split('\n').filter(Boolean).map(step => step.trim());

      if (!messageStatesRef.current.has(messageId)) {
        messageStatesRef.current.set(messageId, {
          prevThinkingProcess: '',
          processedSteps: []
        });
      }

      const messageState = messageStatesRef.current.get(messageId);
      if (thinkingProcess !== messageState.prevThinkingProcess) {
        messageState.prevThinkingProcess = thinkingProcess;
        messageState.processedSteps = newSteps;
        setCurrentSteps(prevSteps => {
          const existingSteps = new Set(prevSteps);
          const uniqueNewSteps = newSteps.filter(step => !existingSteps.has(step));
          return [...prevSteps, ...uniqueNewSteps];
        });
      }
    }
  }, [thinkingProcess, messageId]);

  const renderContent = () => {
    if (!content && thinkingProcess) {
      return (
        <div className="w-full">
          <ThinkingProcess
            messageId={messageId}
            steps={currentSteps}
            isExpanded={isThinkingExpanded}
            onToggle={() => setIsThinkingExpanded(!isThinkingExpanded)}
          />
        </div>
      );
    }

    if (!content) return null;

    return (
        <div className="space-y-4 w-full">
          {/* 显示主要内容 */}
          {text && (
              <div className="whitespace-pre-wrap text-gray-700">{text}</div>
          )}
          <div className="space-y-1">
            {/* 显示链接预览 */}
            {links?.length > 0 && <LinkPreviewList links={links}/>}

            {/* 显示图片内容 */}
            {images?.length > 0 && (
                <div className="w-full max-w-[180px] xs:max-w-[220px] sm:max-w-[280px] md:max-w-[320px]">
                  <div className="w-full">
                    {images.map((image, index) => (
                        <ImageContent
                            key={`${messageId}-img-${index}`}
                            url={image.previewUrl || image.url}
                            index={index}
                        />
                    ))}
                  </div>
                </div>
            )}

            {/* 显示文件内容 */}
            {files?.length > 0 && (
                <div className="flex flex-col space-y-2 w-full max-w-[320px]">
                  {files.map((file, index) => {
                    const isAudio = file.name?.toLowerCase().endsWith('.mp3') ||
                        file.name?.toLowerCase().endsWith('.wav');

                    if (isAudio) {
                      return (
                          <AudioPlayer
                              key={`${messageId}-audio-${index}`}
                              url={file.url}
                              messageText={file.name}
                          />
                      );
                    }

                    return (
                        <div
                            key={`${messageId}-file-${index}`}
                            className="flex items-center justify-between bg-gray-50 rounded-lg p-3 group hover:bg-gray-100 transition-colors cursor-pointer"
                            onClick={() => {
                              const a = document.createElement('a');
                              a.href = file.url;
                              a.download = file.name;
                              a.target = '_blank';
                              a.rel = 'noopener noreferrer';
                              document.body.appendChild(a);
                              a.click();
                              document.body.removeChild(a);
                            }}
                        >
                          <div className="flex items-center space-x-3">
                            <Paperclip className="text-gray-400 group-hover:text-blue-500" size={16}/>
                            <span className="text-gray-700 group-hover:text-blue-600 text-sm">
                      {file.name}
                    </span>
                          </div>
                          <div className="text-gray-400 group-hover:text-blue-500">
                            <Download size={16}/>
                          </div>
                        </div>
                    );
                  })}
                </div>
            )}
          </div>
            {/* 显示思考过程 */}
            {currentSteps.length > 0 && (
                <div className="mt-3 w-full">
                  <ThinkingProcess
                      messageId={messageId}
                      steps={currentSteps}
                      isExpanded={isThinkingExpanded}
                      onToggle={() => setIsThinkingExpanded(!isThinkingExpanded)}
                  />
                </div>
            )}
          </div>
    );  
  };

  return (
      <div className="inline-flex flex-col w-full">
        {renderContent()}
      </div>
  );
};

export default React.memo(MessageContent);
