-- Execute no banco MySQL existente, após backup. Não altera tabelas de alunos nem o legado.


CREATE TABLE IF NOT EXISTS rag_documento (
	id VARCHAR(64) NOT NULL, 
	nome VARCHAR(255) NOT NULL, 
	versao_ativa VARCHAR(32), 
	PRIMARY KEY (id)
)ENGINE=InnoDB CHARSET=utf8mb4

;


CREATE TABLE IF NOT EXISTS rag_versao (
	id VARCHAR(32) NOT NULL, 
	documento_id VARCHAR(64) NOT NULL, 
	hash_arquivo VARCHAR(64) NOT NULL, 
	modelo_embedding VARCHAR(150) NOT NULL, 
	curso VARCHAR(160) NOT NULL, 
	periodo VARCHAR(80) NOT NULL, 
	ano INTEGER, 
	inicio DATE, 
	fim DATE, 
	url_oficial VARCHAR(1000) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(documento_id) REFERENCES rag_documento (id),
	INDEX ix_rag_versao_documento_id (documento_id)
)ENGINE=InnoDB CHARSET=utf8mb4

;


CREATE TABLE IF NOT EXISTS rag_trecho (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	versao_id VARCHAR(32) NOT NULL, 
	pagina INTEGER, 
	texto TEXT NOT NULL, 
	embedding BLOB NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(versao_id) REFERENCES rag_versao (id),
	INDEX ix_rag_trecho_versao_id (versao_id)
)ENGINE=InnoDB CHARSET=utf8mb4

;
