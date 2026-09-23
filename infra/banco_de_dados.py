class BancoDeDados:
    def __init__(self, host: str, usuario: str, senha: str, database: str):
        self.__host = host
        self.__usuario = usuario
        self.__senha = senha
        self.__database = database
        self.__conexao = None  # objeto de conexão MySQL (ex: mysql.connector.connect)

    def conectar(self):
        pass

    def desconectar(self):
        pass

    def executar_query(self, query: str, parametros: tuple = None):
        pass
