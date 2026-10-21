-- Tabela da base de conhecimento do RAG. Rode uma vez no banco do projeto.
CREATE TABLE IF NOT EXISTS trecho_documento (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    hash_arquivo     CHAR(64)     NOT NULL,  -- SHA-256 do PDF: identifica o arquivo pelo conteúdo
    arquivo          VARCHAR(255) NOT NULL,  -- só o nome do arquivo, nunca o caminho da máquina
    pagina           INT UNSIGNED NULL,      -- NULL em formatos sem página (DOCX, TXT)
    texto            TEXT         NOT NULL,  -- trechos têm no máximo ~1200 caracteres
    modelo_embedding VARCHAR(150) NOT NULL,  -- vetores de modelos diferentes não se misturam
    embedding        BLOB         NOT NULL,  -- vetor float32 little-endian
    criado_em        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hash_modelo (hash_arquivo, modelo_embedding),
    INDEX idx_modelo (modelo_embedding)
) CHARACTER SET utf8mb4;
