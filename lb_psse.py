import sys
sys.path.append(r'C:\Program Files (x86)\PTI\PSSE34\PSSPY27')
import psse34
import psspy
import logging
from os import remove, path, makedirs, getcwd, walk
from datetime import datetime

class Text_logger(object):
    """
    Trida pro logovani.
    """
    rel_path = r'\logs\\'

    def __init__(self, day, logtype, log_path=rel_path):
        self.day = day
        self.logtype = logtype
        self.log_path = log_path
        (self.logger, self.handler, self.handlerErr) = self.defineLoggers()

    def defineLoggers(self):
        dirname = getcwd() + self.log_path
        dstr = self.day.strftime("%Y-%m-%d")
        tstr = self.day.strftime('%Y-%m-%dT%H:%M')
        if not path.exists(dirname):
            makedirs(dirname)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.disabled = False
        try:
            handler = logging.FileHandler(dirname + self.logtype + '_info_' +
                                          dstr + '.log')
            handler.setLevel(logging.INFO)
            handlerErr = logging.FileHandler(dirname + self.logtype +
                                             '_errors_' + dstr + '.log')
            handlerErr.setLevel(logging.ERROR)
        except:
            logging.error('defineLoggers:Log file cannot be created')
        formatter = logging.Formatter('%(asctime)s - %(name)s - '
                                      '%(processName)s - %(levelname)s - '
                                      '%(message)s')
        handler.setFormatter(formatter)
        handlerErr.setFormatter(formatter)
        logger.addHandler(handler)
        logger.addHandler(handlerErr)
        logger.info('{0} Starting {1} on {2} {0}\n'.format('*' * 10,
                                                           self.logtype, tstr))
        return (logger, handler, handlerErr)

    def deleteOldLoggers(self):
        # Delete loggers older than 90 days
        path = "logs"
        for r, d, f in walk(path):
            for filename in f:
                date_of_file = datetime.strptime(filename.split('_')[-1][:-4], '%Y-%m-%d')
                if (datetime.now() - date_of_file).days > 90:
                    remove(path + '/' + filename)

    def closeLoggers(self):
        # Close logger
        self.handler.close()
        self.handlerErr.close()
        self.logger.removeHandler(self.handler)
        self.logger.removeHandler(self.handlerErr)
        self.logger.disabled = True

class psseCalc(object):
    """
    Trida s PSS/E funkcemi.
    """

    def load_model_raw(self, model_path, logger):
        """
		Funkce pro nacteni modelu site ve formatu RAW.
		@return: V pripade chyby je potreba proverit API dokumentaci PSS/E
		"""
        filename = model_path.split('\\')[-1]
        with redirected_stdout() as fake_stdout:
            ierr = psspy.readrawversion(0, """32""", model_path)
        if ierr == 0:
            logger.info("Model {} uspesne nacten do PSS/E.".format(filename))
        else:
            logger.error("Model {} nebyl nacten do PSS/E. PSS/E chyba: {}.".format(filename, ierr))
        return

    def dis_isl(self, logger):
        """
		Funkce pro odpojeni vsech elektrickych ostrovu krome toho s definovanym SLACK uzlem.
		@return: V pripade chyby je potreba proverit API dokumentaci PSS/E
		"""
        disconnected_islands = 0
        with redirected_stdout() as fake_stdout:
            ierr, tree = psspy.tree(1, -1)
        if ierr != 0:
            logger.error("PSS/E chyba modelu pri odpojovani ostrovu: {}".format(ierr))
        while tree != 0:
            disconnected_islands += 1
            if ierr != 0:
                logger.error("PSS/E chyba modelu pri odpojovani ostrovu: {}".format(ierr))
                break
            with redirected_stdout() as fake_stdout:
                ierr, tree = psspy.tree(2, 1)
        logger.info("V modelu bylo odpojeno {} ostrovu.".format(disconnected_islands))

    def psse_init(self, logger):
        """
		Inicializuje PSS/E pro vypocty v pripade, ze nebylo inicializovano drive.
		@return: V pripade chyby je potreba proverit API dokumentaci PSS/E
		"""
        with redirected_stdout() as fake_stdout:
            ierr = psspy.psseinit()
        if ierr != 0:
            logger.error("Nepodarilo se spustit PSSE.")
            sys.exit()
        name, major, minor, update, date, stat = psspy.psseversion()
        logger.info("{} ve verzi {}.{}.{} vydano {}.".format(name.replace(" ", ""), major, minor, update, date))
        return

    def calculate_nr(self, model_path, logger):
        """
		PSS/E funkce vyuzivajici Newton-Raphson metodu pro vypocet chodu site. Kombinuje ruzne nastaveni metody,
		aby se pokusila najit reseni.
		@return: Vraci jednotku v pripade chyby. Pro detail chyby je potreba proverit API dokumentaci PSS/E
		"""
        # Automaticke aplikovani mezi jaloviny s non diverge solution
        psspy.save(model_path[:-4] + '.sav')
        psspy.case(model_path[:-4] + '.sav')
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, 1, 99, 1])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, 1, 99]
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
            logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: 1,"
                        " meze jaloveho vykonu aplikovany automaticky, non-divergent solution 1.")
            return 0
        # Automaticke aplikovani mezi jaloviny bez non-divergent reseni.
        psspy.case(model_path[:-4] + '.sav')
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, 1, 99, 0])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < bestsol[0]:
            bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, 1, 99]
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
            logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: 1,"
                        " meze jaloveho vykonu aplikovany automaticky, non-divergent solution 0.")
            return 0
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, 0, 99, 1])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, 1, 99]
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
            logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: 0,"
                        " meze jaloveho vykonu aplikovany automaticky, non-divergent solution 1.")
            return 0
        # Automaticke aplikovani mezi jaloviny bez non-divergent reseni.
        psspy.case(model_path[:-4] + '.sav')
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, 0, 99, 0])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < bestsol[0]:
            bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, 1, 99]
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
            logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: 0,"
                        " meze jaloveho vykonu aplikovany automaticky, non-divergent solution 0.")
            return 0
        # Aplikovani mezi jaloviny pri ruznych iteracich
        iteration = range(20)
        for flatstart in [0, 1]:
            for nondivergentsolution in [0, 1]:
                for varlimits in iteration:
                    psspy.case(model_path[:-4] + '.sav')
                    with redirected_stdout() as fake_stdout:
                        ierr = psspy.fnsl([0, 0, 0, 0, 0, flatstart, varlimits, nondivergentsolution])
                    if ierr != 0:
                        logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
                        return 1
                    ierr, ibus, cmpval = psspy.maxmsm()
                    if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < bestsol[0]:
                        bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, flatstart, varlimits]
                    if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
                        logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: {},"
                                    " Aplikace mezi Q pri iteraci: {}, , non-divergent solution {}.".format(flatstart, varlimits, nondivergentsolution))
                        return 0
        psspy.case(model_path[:-4] + '.sav')
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, 1, -1, 0])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < bestsol[0]:
            bestsol = [(cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5, 1, -1]
        if (cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5 < 0.1 and ierr == 0:
            logger.info("Newton Raphson Load Flow reseni nalezeno. Flatstart: {},"
                        " meze jaloveho vykonu ignorovany, non-divergent solution 0.".format(flatstart))
            return 0
        psspy.case(model_path[:-4] + '.sav')
        with redirected_stdout() as fake_stdout:
            ierr = psspy.fnsl([0, 0, 0, 0, 0, bestsol[1], bestsol[2], 0])
        if ierr != 0:
            logger.error("Chyba modelu pri vypoctu chodu site. PSS/E chyba: {}".format(ierr))
            return 1
        ierr, ibus, cmpval = psspy.maxmsm()
        logger.error("Newton Raphson Load Flow reseni modelu nebylo nalezeno. "
                     "Maximalni meziiteracni chyba: {}".format((cmpval.real ** 2 + cmpval.imag ** 2) ** 0.5))
        return 1

    def save_raw32(self, dest, logger):
        print(dest)
        ierr = psspy.writerawversion(r"""32""", 0, dest)
        logger.info("Model v raw format ulozen.")
        if ierr != 0:
            logger.error("Ulozeni PSSE v raw formatu selhalo error: %s", ierr)


class redirected_stdout(object):
    """
    Objekt pro presmerovani vystupu do promenne.
    """

    def __init__(self):
        """
        Init metoda objektu.
        """
        self._stdout = None
        self._bytes_io = None

    def __enter__(self):
        """
        Enter metoda pro vyuziti s funkci open.
        @return:
        """
        from io import BytesIO
        self._stdout = sys.stdout
        sys.stdout = self._bytes_io = BytesIO()
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        """
        Exit metoda objektu pro vyuziti s funkci open.
        @param exception_type: Druh vyjimky.
        @param exception_value: Hodnota vyjimky.
        @param exception_traceback: Tracback vyjimky.
        @return: N/A
        """
        sys.stdout = self._stdout

    def __str__(self):
        """
        Reprezentace objektu.
        @return: Vraci string obsahuju vse vypsane do standartniho vystupu.
        """
        return self._bytes_io.getvalue()