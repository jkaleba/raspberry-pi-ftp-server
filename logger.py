import logging

class Logger:
    _logger = None

    @staticmethod
    def init(log_file='ftp_server.log'):
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        Logger._logger = logging.getLogger()

    @staticmethod
    def log_info(message):
        Logger._logger.info(message)

    @staticmethod
    def log_warning(message):
        Logger._logger.warning(message)
    
    @staticmethod
    def log_error(message):
        Logger._logger.error(message)
