import json
import uuid
from typing import List, Optional, BinaryIO, Dict

import os
from dataclasses import dataclass
from openai import OpenAI
import numpy as np


@dataclass
class RAGConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 3
    openai_embedding_model: str = "text-embedding-ada-002"
    ollama_embedding_model: str = "bge-m3"
    vector_store: str = "faiss"


@dataclass
class AgentInput:
    query: str
    context: Optional[str] = None
    documents: List[str] = None

    def validate(self):
        if not self.query.strip():
            raise ValueError("查询不能为空")

@dataclass
class RAGModel:
    rag_config: RAGConfig = RAGConfig()

    def validate(self):
        if not self.rag_config:
            raise ValueError("RAG配置不能为空")


@dataclass
class RAGInput(AgentInput):
    documents: List[str]

    def validate(self):
        super().validate()
        if not self.documents:
            raise ValueError("文档列表不能为空")


class Documents:
    """
    用于读取已分好类的 JSON 格式文档。
    """

    def __init__(self, path: str = '') -> None:
        self.path = path

    def get_content(self):
        """
        读取 JSON 格式的文档内容。
        :return: JSON 文档的内容
        """
        with open(self.path, mode='r', encoding='utf-8') as f:
            content = json.load(f)
        return content


class VectorStore:
    def __init__(self, model, document: List[str] = None) -> None:
        """
        初始化向量存储类，存储文档和对应的向量表示，并生成唯一的文档ID。
        :param document: 文档列表，默认为空。
        """
        if document is None:
            document = []
        self.document = document  # 存储文档内容
        self.model = model
        self.vectors = []  # 存储文档的向量表示
        self.doc_ids = []  # 存储文档的唯一ID
        self.vector_ids = []  # 存储向量块的唯一ID

        # 为每个文档生成唯一ID
        self.doc_ids = [str(uuid.uuid4()) for _ in self.document]

    def get_vector(self, EmbeddingModel, model) -> List[Dict[str, List[float]]]:
        """
        使用传入的 Embedding 模型将文档向量化，并生成唯一的向量块ID。
        :param EmbeddingModel: 传入的用于生成向量的模型。
        :return: 返回文档对应的向量列表，每个向量都附带一个ID。
        """
        # 为每个文档生成向量并生成唯一向量块ID
        self.vectors = [EmbeddingModel.get_embedding(doc, model) for doc in self.document]
        self.vector_ids = [str(uuid.uuid4()) for _ in self.vectors]
        # 返回包含向量及其对应ID的字典
        return [{"vector_id": vec_id, "vector": vector} for vec_id, vector in zip(self.vector_ids, self.vectors)]

    def persist(self, path: str = 'storage'):
        """
        将文档、向量、文档ID和向量ID持久化到本地目录中，以便后续加载使用。
        :param path: 存储路径，默认为 'storage'。
        """
        if not os.path.exists(path):
            os.makedirs(path)  # 如果路径不存在，创建路径
        # 保存向量为 numpy 文件
        np.save(os.path.join(path, 'vectors.npy'), self.vectors)
        # 将文档内容和文档ID存储到文本文件中
        with open(os.path.join(path, 'documents.txt'), 'w', encoding='utf-8') as f:
            for doc, doc_id in zip(self.document, self.doc_ids):
                f.write(f"{doc_id}\t{doc}\n")
        # 将向量ID存储到文本文件中
        with open(os.path.join(path, 'vector_ids.txt'), 'w', encoding='utf-8') as f:
            for vector_id in self.vector_ids:
                f.write(f"{vector_id}\n")

    def load_vector(self, path: str = 'storage'):
        """
        从本地加载之前保存的文档、向量、文档ID和向量ID数据。
        :param path: 存储路径，默认为 'storage'。
        """
        # 加载保存的向量数据
        self.vectors = np.load(os.path.join(path, 'vectors.npy')).tolist()
        # 加载文档内容和文档ID
        with open(os.path.join(path, 'documents.txt'), 'r', encoding='utf-8') as f:
            self.document = []
            self.doc_ids = []
            for line in f.readlines():
                doc_id, doc = line.strip().split('\t', 1)
                self.doc_ids.append(doc_id)
                self.document.append(doc)
        # 加载向量ID
        with open(os.path.join(path, 'vector_ids.txt'), 'r', encoding='utf-8') as f:
            self.vector_ids = [line.strip() for line in f.readlines()]

    def get_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        计算两个向量的余弦相似度。
        :param vector1: 第一个向量。
        :param vector2: 第二个向量。
        :return: 返回两个向量的余弦相似度，范围从 -1 到 1。
        """
        dot_product = np.dot(vector1, vector2)
        magnitude = np.linalg.norm(vector1) * np.linalg.norm(vector2)
        if not magnitude:
            return 0
        return dot_product / magnitude

    def query(self, query: str, EmbeddingModel, k: int = 1) -> List[Dict[str, str]]:
        """
        根据用户的查询文本，检索最相关的文档片段。
        :param query: 用户的查询文本。
        :param EmbeddingModel: 用于将查询向量化的嵌入模型。
        :param k: 返回最相似的文档数量，默认为 1。
        :return: 返回包含文档ID和文档内容的最相似文档列表。
        """
        # 将查询文本向量化
        query_vector = EmbeddingModel.get_embedding(query, model=self.model)
        # 计算查询向量与每个文档向量的相似度
        similarities = [self.get_similarity(query_vector, vector) for vector in self.vectors]
        # 获取相似度最高的 k 个文档索引
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        # 返回对应的文档ID和内容
        result = [{"doc_id": self.doc_ids[idx], "document": self.document[idx]} for idx in top_k_indices]
        print("和问题最相近的文本块内容:" + str(result))
        return result

    def print_info(self):
        """
        输出存储在 VectorStore 中的文档、向量、文档ID和向量ID的详细信息。
        """
        print("===== 存储的信息 =====")
        for i, (doc_id, doc, vector_id, vector) in enumerate(
                zip(self.doc_ids, self.document, self.vector_ids, self.vectors)):
            print(f"文档 {i + 1}:")
            print(f"  文档ID: {doc_id}")
            print(f"  文档内容: {doc}")
            print(f"  向量ID: {vector_id}")
            print(f"  向量表示: {vector}")
            print("=======================")


class EmbeddingModel:
    """
    向量模型客户端
    """
    def __init__(self, model_name, api_key) -> None:
        """
        根据参数配置来选择ollama客户端还是GPT客户端
        """
        self.model_name = model_name
        self.api_key = api_key
        self.client = OpenAI(
            base_url="https://api.openai.com/v1",
            api_key=self.api_key
        ) if model_name.startswith("gpt") else OpenAI(
            base_url="http://localhost:11434/v1/",
            api_key="ollama"
        )

    def get_embedding(self, text: str, model) -> List[float]:
        """
        text (str) - 需要转化为向量的文本

        return：list[float] - 文本的向量表示
        """
        # ollama-使用的 ollama 的模型名称，“bge-m3”  gpt-使用的是默认的“text-embedding-3-small”
        return self.client.embeddings.create(
            input=[text],
            model=model
        ).data[0].embedding


@dataclass
class FileConfig:
    allowed_types: List[str] = None
    max_size: int = 10 * 1024 * 1024  # 10MB
    chunk_size: int = 1024

    def validate_file(self, file: BinaryIO) -> bool:
        if self.allowed_types and not any(file.name.endswith(t) for t in self.allowed_types):
            raise ValueError(f"不支持的文件类型，仅支持: {', '.join(self.allowed_types)}")
        if file.tell() > self.max_size:
            raise ValueError(f"文件大小超过限制: {self.max_size / (1024 * 1024)}MB")
        return True


class FileUploader:
    def __init__(self, save_dir: str, config: FileConfig = None):
        self.save_dir = save_dir
        self.config = config or FileConfig()
        os.makedirs(save_dir, exist_ok=True)

    def upload(self, file: BinaryIO) -> str:
        """上传文件并返回保存路径"""
        self.config.validate_file(file)
        filepath = os.path.join(self.save_dir, file.name)

        with open(filepath, 'wb') as f:
            while chunk := file.read(self.config.chunk_size):
                f.write(chunk)
        return filepath


@dataclass
class RAGInput:
    """
    documents_path: 文件目录地址/文件路径
    query:用户的问题
    """
    documents_path: str
    query: str

    def validate(self):
        super().validate()
        if not self.documents_path:
            raise ValueError("必须提供文档")


class BaseRAG:
    """RAG基类，提供基础的资源管理功能"""

    def cleanup(self):
        """清理RAG实例和相关资源"""
        try:
            if hasattr(self, 'rag') and self.rag is not None:
                # 清理向量存储资源
                if hasattr(self.rag, 'vector_store') and self.rag.vector_store is not None:
                    self.rag.vector_store.cleanup()

                # 清理 embedding 相关资源
                if hasattr(self.rag, 'embedding_func'):
                    self.rag.embedding_func = None

                # 清理 RAG 实例
                self.rag = None

            # 手动触发垃圾回收
            import gc
            gc.collect()

            # 清理 CUDA 缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

            if hasattr(self, 'logger'):
                self.logger.info("RAG资源已清理完成")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"清理RAG资源时出错: {str(e)}")
            raise

    def __del__(self):
        """析构函数，确保资源被清理"""
        self.cleanup()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口，确保资源被清理"""
        self.cleanup()