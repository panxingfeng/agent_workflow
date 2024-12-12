from openai import OpenAI

from config.bot import RAG_PROMPT_TEMPLATE
from agent_workflow.llm.llm import LLM
from agent_workflow.rag.base import RAGConfig, RAGInput, VectorStore, EmbeddingModel
from agent_workflow.utils.read_files import ReadFiles

class GeneralRAG:
    def __init__(self, llm: tuple[OpenAI, str, str], rag_config: RAGConfig, verbose: bool = False,
                 stream: bool = False):
        self.rag_config = rag_config
        self.llm, self.model_name, self.api_key = llm
        self.prompt = RAG_PROMPT_TEMPLATE
        self.verbose = verbose
        self.stream = stream

    def execute(self, input_data: RAGInput, k: int = 1, save=False, print_info=False) -> str:
        """
        执行 RAG 流程：文件上传、文档分块、向量化、检索和生成答案。

        :param print_info: 是否打印向量信息
        :param save: 是否将向量和文档保存到本地
        :param k: 返回与问题最相关的k个文档片段，默认为1
        :param input_data: RAGInput 对象 包含问题，文档地址
        :return: 生成的答案字符串
        """
        try:
            # 加载并切分文档
            docs = ReadFiles(input_data.documents_path).get_content(
                max_token_len=self.rag_config.chunk_size,
                cover_content=self.rag_config.chunk_overlap
            )
            vector = VectorStore(document=docs,
                                 model=self.rag_config.openai_embedding_model if self.model_name.lower().startswith(
                                     "gpt") else self.rag_config.ollama_embedding_model)

            # 创建向量模型客户端
            embedding = EmbeddingModel(
                model_name=self.model_name,
                api_key=self.api_key
            )
            vector.get_vector(EmbeddingModel=embedding,
                              model=self.rag_config.openai_embedding_model if self.model_name.lower().startswith(
                                  "gpt") else self.rag_config.ollama_embedding_model)

            if save:
                vector.persist(path='file/storage')

            if print_info:
                vector.print_info()

            # 在数据库中检索最相关的文档片段
            content = vector.query(input_data.query, EmbeddingModel=embedding, k=k)[0]

            # 使用大模型进行回复
            answer = LLM(stream=self.stream).chat(
                message=self.prompt['prompt_template'].format(question=input_data.query, history=None, context=content),
                prompt="", is_gpt=True if self.model_name.lower().startswith("gpt") else False)

            return answer

        except Exception as e:
            print("RAGExecutor 执行失败，详细错误信息:", str(e))
            raise Exception(f"RAG处理失败: {str(e)}") from e
