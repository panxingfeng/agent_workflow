import { useCallback, useState } from 'react';
import {UPLOAD_CONFIG} from '../constants';

export const useFileUpload = () => {
  const [uploadedImages, setUploadedImages] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [errors, setErrors] = useState([]);

  const handleImageUpload = useCallback(async (e) => {
    const files = Array.from(e.target.files || []);
    const newErrors = [];
    const validImages = [];
    const { maxImageCount } = UPLOAD_CONFIG;

    if (uploadedImages.length + files.length > maxImageCount) {
      newErrors.push({ error: `最多只能上传${maxImageCount}张图片` });
      setErrors(newErrors);
      return;
    }

    files.forEach((file) => {
      if (file.file && file.file.serverPath) {
        validImages.push({
          file: file.file,
          previewUrl: file.file.serverUrl,
          name: file.name || file.file.name,
          size: file.size,
          type: file.type,
          uploadTime: new Date().toISOString()
        });
      }
    });

    if (validImages.length > 0) {
      setUploadedImages(prev => {
        const updatedImages = [...prev, ...validImages];
        return updatedImages.slice(0, maxImageCount);
      });
    }

    if (newErrors.length > 0) {
      setErrors(newErrors);
    }

    if (e.target) e.target.value = '';
  }, [uploadedImages]);

  const handleFileUpload = useCallback(async (e) => {
    const files = Array.from(e.target.files || []);
    const newErrors = [];
    const validFiles = [];
    const { maxFileCount } = UPLOAD_CONFIG;

    if (uploadedFiles.length + files.length > maxFileCount) {
      newErrors.push({ error: `最多只能上传${maxFileCount}个文件` });
      setErrors(newErrors);
      return;
    }

    files.forEach((file) => {
      if (file.serverUrl) {
        validFiles.push({
          file: {
            name: file.name,
            serverPath: file.serverPath,
            serverUrl: file.serverUrl
          },
          name: file.name,
          size: file.size,
          type: file.type,
          previewUrl: file.serverUrl,
          uploadTime: new Date().toISOString()
        });
      }
    });

    if (validFiles.length > 0) {
      setUploadedFiles(prev => {
        const updatedFiles = [...prev, ...validFiles];
        return updatedFiles.slice(0, maxFileCount);
      });
    }

    if (newErrors.length > 0) {
      setErrors(newErrors);
    }

    if (e.target) e.target.value = '';
  }, [uploadedFiles]);

  const handleDeleteImage = useCallback((index) => {
    setUploadedImages(prev => {
      const newImages = [...prev];
      newImages.splice(index, 1);
      return newImages;
    });
  }, []);

  const handleDeleteFile = useCallback((index) => {
    setUploadedFiles(prev => {
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  const clearUploads = useCallback(() => {
    setUploadedImages([]);
    setUploadedFiles([]);
    setErrors([]);

    if (typeof window !== 'undefined') {
      document.querySelectorAll('input[type="file"]').forEach(input => {
        input.value = '';
      });
    }
  }, []);

  const getUploadedFiles = useCallback(() => {
    return {
      images: uploadedImages.map(img => ({
        file: img.file,
        name: img.name,
        type: img.type,
        size: img.size
      })),
      files: uploadedFiles.map(file => ({
        file: file.file,
        name: file.name,
        type: file.type,
        size: file.size
      }))
    };
  }, [uploadedImages, uploadedFiles]);

  const stats = {
    totalImages: uploadedImages.length,
    totalFiles: uploadedFiles.length,
    totalSize: [...uploadedImages, ...uploadedFiles]
      .reduce((acc, curr) => acc + curr.size, 0),
    remainingImageSlots: UPLOAD_CONFIG.maxImageCount - uploadedImages.length,
    remainingFileSlots: UPLOAD_CONFIG.maxFileCount - uploadedFiles.length
  };

  return {
    uploadedImages,
    uploadedFiles,
    errors,
    stats,
    handleImageUpload,
    handleFileUpload,
    handleDeleteImage,
    handleDeleteFile,
    clearErrors,
    clearUploads,
    getUploadedFiles
  };
};