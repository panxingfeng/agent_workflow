export const ASSISTANT_TITLE = "AI智能助手";
export const ASSISTANT_DESCRIPTION = "可以帮你完成各种任务，包括写作、分析、编程等。";

// 上传配置
export const UPLOAD_CONFIG = {
  maxImageSize: 5 * 1024 * 1024, // 5MB
  maxFileSize: 10 * 1024 * 1024, // 10MB
  maxImageCount: 5,
  maxFileCount: 5,
  allowedImageTypes: [
    'images/jpeg',
    'images/png',
    'images/gif',
    'images/webp'
  ],
  allowedFileTypes: [
    'text/plain',
    'application/json',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/markdown'
  ]
};

// API配置
export const API_CONFIG = {
  baseUrl_port:'http://localhost:8000',
  baseUrl: 'http://localhost:8000/api',
  endpoints: {
    chat: '/chat',
  },
  timeout: 30000 // 30秒超时
};
