import { useState, useCallback, useRef } from 'react';
import { API_CONFIG } from '../constants';

export const useChatHistory = () => {
  const [histories, setHistories] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const abortControllerRef = useRef(null);
  const isRequestingRef = useRef(false);

  const fetchHistories = useCallback(async ({
    search = ''
  } = {}) => {
    try {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      if (isRequestingRef.current) {
        return;
      }

      isRequestingRef.current = true;
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_CONFIG.baseUrl}/chat/history`);

      if (!response.ok) {
        throw new Error(`Failed to fetch histories: ${response.statusText}`);
      }

      const data = await response.json();

      const filteredHistories = search
        ? data.filter(history =>
            history.title?.toLowerCase().includes(search.toLowerCase()) ||
            history.messages?.some(msg =>
              msg.query?.toLowerCase().includes(search.toLowerCase()) ||
              msg.response?.toLowerCase().includes(search.toLowerCase())
            )
          )
        : data;

      setHistories(filteredHistories);
      return filteredHistories;

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Request was aborted');
        return;
      }
      console.error('Error fetching histories:', error);
      setError(error.message);
      return [];
    } finally {
      isRequestingRef.current = false;
      setIsLoading(false);
    }
  }, []);

  const updateHistory = useCallback(async (messageId, updates) => {
    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/chat/history/${messageId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        throw new Error(`Failed to update history: ${response.statusText}`);
      }

      // 乐观更新本地状态
      setHistories(prev =>
        prev.map(history =>
          history.message_id === messageId
            ? { ...history, ...updates }
            : history
        )
      );

      return await response.json();
    } catch (error) {
      console.error('Error updating history:', error);
      setError(error.message);
      throw error;
    }
  }, []);

  const deleteHistory = useCallback(async (conversationId) => {
    try {
      const response = await fetch(`${API_CONFIG.baseUrl}/chat/history/${conversationId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`Failed to delete history: ${response.statusText}`);
      }

      setHistories(prev =>
        prev.filter(history => history.conversation_id !== conversationId)
      );

      return await response.json();
    } catch (error) {
      console.error('Error deleting history:', error);
      setError(error.message);
      throw error;
    }
  }, []);

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    isRequestingRef.current = false;
    setIsLoading(false);
    setError(null);
  }, []);

  return {
    histories,
    isLoading,
    error,
    fetchHistories,
    updateHistory,
    deleteHistory,
    cleanup
  };
};