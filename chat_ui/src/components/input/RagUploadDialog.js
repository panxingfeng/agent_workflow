import React, { useState, useRef, useEffect} from 'react';
import { Modal } from 'antd';
import { Database, Upload, XCircle, Eye, Loader2, Pencil } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { API_CONFIG } from "../../constants";

const RagUploadDialog = ({ onFilesUploaded, onRagUse }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState([]);
  const [isFinished, setIsFinished] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [isUsed, setIsUsed] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [ragName, setRagName] = useState('');
  const [isNaming, setIsNaming] = useState(false);
  const [existingRags, setExistingRags] = useState([]);
  const [ragsInfo, setRagsInfo] = useState([]);
  const [currentRagName, setCurrentRagName] = useState(new Set());
  const [expandedRags, setExpandedRags] = useState(new Set());
  const inputRef = useRef(null);

  const handleFileInput = async (e) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (!selectedFiles.length) return;

    setUploading(true);
    try {
      const formData = new FormData();
      selectedFiles.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch(`${API_CONFIG.baseUrl}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Upload failed: ${errorText}`);
      }

      const result = await response.json();

      if (result.files && result.files.length > 0) {
        const newFiles = selectedFiles.map((originalFile, index) => ({
          name: originalFile.name,
          size: originalFile.size,
          serverPath: result.files[index].path,
          serverUrl: result.files[index].url
        }));

        setFiles(prev => [...prev, ...newFiles]);
        setIsFinished(false);
        setIsUsed(false);
      }
    } catch (error) {
      console.error('文件上传失败:', error);
      alert(error.message || '文件上传失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteSingleFile = async (index) => {
    try {
      const file = files[index];
      if (file?.serverPath) {
        await fetch(`${API_CONFIG.baseUrl}/delete?path=${encodeURIComponent(file.serverPath)}`, {
          method: 'DELETE'
        });
      }
      const newFiles = files.filter((_, i) => i !== index);
      setFiles(newFiles);
      if (newFiles.length === 0) {
        setIsFinished(false);
        setIsUsed(false);
        setRagName('');
      }
    } catch (error) {
      console.error('文件删除失败:', error);
      alert('文件删除失败，请重试');
    }
  };

  const handleDeleteFileGroup = async () => {
    const showConfirmationDialog = (message) => {
      return new Promise((resolve) => {
        Modal.confirm({
          title: '确认操作',
          content: message,
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
    };

    const userConfirmed = await showConfirmationDialog(
      "此操作会删除上传的文件和已完成的本地RAG文件，是否继续？"
    );

    if (!userConfirmed) return;

    try {
      const deleteFilePromises = files.map(async (file) => {
        if (file?.serverPath) {
          await fetch(`${API_CONFIG.baseUrl}/delete?path=${encodeURIComponent(file.serverPath)}`, {
            method: 'DELETE',
          });
        }
      });

      await Promise.all(deleteFilePromises);

      if (isUsed && ragName) {
        await fetch(`${API_CONFIG.baseUrl}/rag/delete`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            rag_name: ragName,
          }),
        });
      }

      setFiles([]);
      setIsFinished(false);
      setIsUsed(false);
      setRagName('');
      setIsNaming(false);
      setShowPreview(false);

      alert('文件删除成功');
    } catch (error) {
      console.error('文件删除失败:', error);
      alert('文件删除失败，请重试');
    }
  };

  const handleFinish = () => {
    if (files.length > 0) {
      setIsFinished(true);
      setShowPreview(false);
      setRagName(getDisplayName(files[0].name));
      setIsNaming(true);
    }
  };

  const loadRags = async () => {
    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/rag/list`);
      if (response.ok) {
        const data = await response.json();
        setExistingRags(data.rags.map(rag => rag.name));
        setRagsInfo(data.rags);
      }
    } catch (error) {
      console.error('加载知识库列表失败:', error);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadRags();
    }
  }, [isOpen]);

  const handleRename = async (newName) => {
    if (!ragName.trim() || !newName.trim()) return;

    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/rag/rename`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          old_name: ragName,
          new_name: newName
        })
      });

      if (!response.ok) {
        throw new Error('重命名失败');
      }

      setRagName(newName);
      await loadRags();
    } catch (error) {
      console.error('重命名失败:', error);
      alert(error.message);
    }
  };

  const handleConfirmName = () => {
    if (!ragName.trim()) return;

    if (isUsed) {
      handleRename(ragName);
    }
    setIsNaming(false);
  };

  const handleRagProcess = async () => {
    if (processing) return;

    if (!ragName || !files.length) {
      alert('请确保已输入知识库名称且已上传文件');
      return;
    }

    setProcessing(true);
    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/rag/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          files: files.map(file => file.serverPath),
          rag_name: ragName
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const result = await response.json();

      if (result.success) {
        // 更新当前使用的知识库集合
        setCurrentRagName(prev => {
          const newSet = new Set(prev);
          newSet.add(ragName);
          return newSet;
        });
        onRagUse?.(ragName);

        // 重新加载知识库列表并清理状态
        await loadRags();
        setFiles([]);
        setIsFinished(false);
        setIsUsed(false);
        setRagName('');
        setIsNaming(false);
        setShowPreview(false);

        if (result.skipped) {
          alert('知识库已存在，已自动启用');
        } else {
          alert('知识库处理成功');
        }
      }
    } catch (error) {
      console.error('RAG处理失败:', error);
      alert(error.message || 'RAG处理失败，请重试');
    } finally {
      setProcessing(false);
    }
  };

  const toggleRagDetails = (ragName) => {
    setExpandedRags(prev => {
      const newSet = new Set(prev);
      if (newSet.has(ragName)) {
        newSet.delete(ragName);
      } else {
        newSet.add(ragName);
      }
      return newSet;
    });
  };

  const getDisplayName = (filename) => {
    return filename.split('.').slice(0, -1).join('.');
  };

  const handleDeleteRag = async (ragName) => {
    const showConfirmationDialog = (message) => {
      return new Promise((resolve) => {
        Modal.confirm({
          title: '确认操作',
          content: message,
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
    };

    const userConfirmed = await showConfirmationDialog(
      "确定要删除此知识库吗？此操作不可恢复。"
    );

    if (!userConfirmed) return;

    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/rag/delete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rag_name: ragName,
        }),
      });

      if (!response.ok) {
        throw new Error('删除失败');
      }

      // 从使用集合中移除
      setCurrentRagName(prev => {
        const newSet = new Set(prev);
        newSet.delete(ragName);
        return newSet;
      });
      onRagUse?.(null);

      await loadRags();
      alert('知识库删除成功');
    } catch (error) {
      console.error('删除知识库失败:', error);
      alert(error.message || '删除知识库失败，请重试');
    }
  };

  const renderNameInput = () => (
    <div className="flex gap-2 items-center">
      <Input
        value={ragName}
        onChange={(e) => setRagName(e.target.value)}
        placeholder="请输入知识库名称"
        className="flex-1"
        onKeyPress={(e) => {
          if (e.key === 'Enter') {
            handleConfirmName();
          }
        }}
      />
      <Button
        size="sm"
        onClick={handleConfirmName}
        disabled={!ragName.trim()}
      >
        确认
      </Button>
    </div>
  );

 return (
  <Dialog open={isOpen} onOpenChange={setIsOpen}>
    <DialogTrigger asChild>
      <Button
        variant="outline"
        size="sm"
        className="flex items-center gap-2 bg-white hover:bg-gray-50"
      >
        <Database size={16} />
        <span>上传知识库</span>
      </Button>
    </DialogTrigger>

    <DialogContent className="sm:max-w-[600px] bg-white">
      <DialogHeader>
        <DialogTitle>上传知识库文件</DialogTitle>
      </DialogHeader>

      <div className="space-y-4">
        {/* 1. 文件上传按钮 */}
        <div className="flex justify-between items-center">
          <Button
            variant="outline"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="bg-white hover:bg-gray-50"
          >
            <Upload size={16} className="mr-2" />
            选择文件
          </Button>

          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileInput}
            accept=".pdf,.txt,.doc,.docx"
          />
        </div>

        {/* 2. 知识库名称输入和文件列表 */}
        {files.length > 0 && !isUsed && (
          <div className="bg-gray-50 p-3 rounded-lg">
            {isFinished ? (
              <div className="space-y-2">
                {/* 命名输入框 */}
                {isNaming ? (
                  renderNameInput()
                ) : (
                  <div className="flex items-center justify-between px-2 py-1 bg-white rounded-lg">
                    <span className="text-sm font-medium">{ragName}</span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (existingRags.includes(ragName)) {
                            setCurrentRagName(ragName);
                            onRagUse?.(ragName);
                            alert('知识库已存在，已自动启用');
                            // 清除上传状态
                            setFiles([]);
                            setIsFinished(false);
                            setIsUsed(false);
                            setRagName('');
                            setIsNaming(false);
                            setShowPreview(false);
                          } else {
                            handleRagProcess();
                          }
                        }}
                        disabled={processing || !ragName || !files.length}
                        className={`text-sm ${
                          processing ? 'text-gray-400' : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        {processing ? (
                          <>
                            <Loader2 size={14} className="mr-1 animate-spin"/>
                            处理中...
                          </>
                        ) : '使用'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleDeleteFileGroup}
                        disabled={processing}
                        className="text-gray-500 hover:text-red-600"
                      >
                        <XCircle size={16} />
                      </Button>
                    </div>
                  </div>
                )}

                {/* 文件列表 */}
                <div className="flex flex-wrap gap-2">
                  {files.map((file, index) => (
                    <div
                      key={index}
                      className="inline-flex items-center bg-white rounded-lg px-3 py-1 text-sm border border-gray-200"
                    >
                      <span className="truncate max-w-[120px]">{file.name}</span>
                      <span className="text-gray-400 mx-1">
                        ({(file.size / 1024 / 1024).toFixed(2)}MB)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {/* 文件上传列表 */}
                <div className="flex flex-wrap gap-2">
                  {files.map((file, index) => (
                    <div
                      key={index}
                      className="inline-flex items-center bg-white rounded-lg px-3 py-1 text-sm border border-gray-200"
                    >
                      <span className="truncate max-w-[120px]">{file.name}</span>
                      <span className="text-gray-400 mx-1">
                        ({(file.size / 1024 / 1024).toFixed(2)}MB)
                      </span>
                      <button
                        onClick={() => handleDeleteSingleFile(index)}
                        className="ml-1 p-1 hover:bg-gray-100 rounded-full"
                      >
                        <XCircle size={14} className="text-gray-400"/>
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex justify-end pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleFinish}
                    className="text-gray-600 hover:text-gray-800"
                  >
                    完成
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 3. 知识库列表始终在最下方 */}
        {ragsInfo.length > 0 && (
          <div className="bg-gray-50 p-3 rounded-lg">
            <div className="text-sm font-medium mb-2">已有知识库：</div>
            <div className="min-w-full">
              <div className="grid grid-cols-6 gap-4 px-4 py-2 bg-gray-100 rounded-t-lg text-sm font-medium text-gray-600">
                <div className="col-span-2">名称</div>
                <div className="col-span-2">创建时间</div>
                <div className="col-span-2 text-right">操作</div>
              </div>
              <div className="bg-white">
                {ragsInfo.map((rag, index) => (
                  <div
                    key={index}
                    className={`grid grid-cols-6 gap-4 px-4 py-3 items-center border-b text-sm
                      ${index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
                  >
                    <div className="col-span-2 flex items-center gap-2">
                      <span className="font-medium">{rag.name}</span>
                      {currentRagName.has(rag.name) && (
                        <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded">
                          当前使用中
                        </span>
                      )}
                    </div>
                    <div className="col-span-2 text-gray-500">
                      {new Date(rag.created_at).toLocaleString()}
                    </div>
                    <div className="col-span-2 flex justify-end items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className={`text-sm ${
                          currentRagName.has(rag.name)
                            ? 'text-blue-500 hover:text-blue-600' 
                            : 'text-gray-500 hover:text-gray-700'
                        }`}
                        onClick={() => {
                          setCurrentRagName(prev => {
                            const newSet = new Set(prev);
                            if (newSet.has(rag.name)) {
                              newSet.delete(rag.name);
                              onRagUse?.(null);  // 取消使用时传 null
                            } else {
                              newSet.add(rag.name);
                              onRagUse?.(rag.name);
                            }
                            return newSet;
                          });
                        }}
                      >
                        {currentRagName.has(rag.name) ? '取消使用' : '使用'}
                      </Button>
                      {rag.files_info && rag.files_info.length > 0 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-gray-500 hover:text-gray-700"
                          onClick={() => toggleRagDetails(rag.name)}
                        >
                          <Eye size={16} />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-gray-500 hover:text-red-600"
                        onClick={() => handleDeleteRag(rag.name)}
                      >
                        <XCircle size={16} />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            {/* 文件详情展开部分 */}
            {ragsInfo.map((rag, index) => (
              expandedRags.has(rag.name) && rag.files_info && rag.files_info.length > 0 && (
                <div key={`detail-${index}`} className="mt-1 p-3 bg-gray-100 rounded-lg">
                  <div className="text-sm text-gray-600">包含文件：</div>
                  <div className="grid grid-cols-6 gap-4 mt-2 text-sm">
                    {rag.files_info.map((file, fileIndex) => (
                      <div key={fileIndex} className="col-span-6 flex justify-between items-center bg-white px-3 py-2 rounded">
                        <span className="text-gray-700">{file.name} ({(file.size / 1024).toFixed(2)}KB)</span>
                        <span className="text-gray-400">
                          {new Date(file.created_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            ))}
          </div>
        )}
      </div>
    </DialogContent>
  </Dialog>
);
};

export default RagUploadDialog;