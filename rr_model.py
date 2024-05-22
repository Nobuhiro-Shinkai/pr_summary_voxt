import fasteners
import random
import logging
from pathlib import Path


class RoundRobinModel:
    EXCLUSIVE_LOCK = './lockcount'
    COUNT_FILE  = './count'
    FILESIZE = 2

    def __init__(self, config):
        self.logger_ = logging.getLogger("pr_summary.rr_model")
        self.logger_.debug("dosummary OPENAI_KEYS:{}".format(config['OPENAI_KEYS']))
        self.modelcount = int(config['OPENAI_KEYS'])
        self.models = []
        for i in range(self.modelcount):
            key = config['OPENAI_API_KEY' + str(i+1)]
            base = config['OPENAI_API_BASE' + str(i+1)]
            #self.logger_.debug("dosummary base:{} key:{}".format(base, key))
            self.models.append((base, key))
        self.lock = fasteners.InterProcessLock(RoundRobinModel.EXCLUSIVE_LOCK)
        self._init_count()

    def get_current_model(self):
        count = self._get_current_count()
        return self.models[count]
    
    def _init_count(self):
        self.lock.acquire()
        p = Path(RoundRobinModel.COUNT_FILE)
        if not p.exists() or p.stat().st_size != RoundRobinModel.FILESIZE:
            try:
                # ファイルがない場合、ランダムな値をセット
                count = random.randint(0, self.modelcount-1)
                with open(RoundRobinModel.COUNT_FILE, "wb") as f:
                    f.write(count.to_bytes(2, 'little'))    
            except:
                self.logger_.error("", exc_info=True)
        self.lock.release()
    
    def _get_current_count(self):
        count = 0
        self.lock.acquire()
        try:
            with open(RoundRobinModel.COUNT_FILE, "rb") as f:
                #mmap.mmap(fileno, length[, tagname[, access[, offset]]])  指定されたファイルから length バイトをマップする。 
                #length が 0 の場合、マップの最大の長さは現在のファイルサイズになります。
                data = f.read()
                count = int.from_bytes(data, byteorder='little')
            with open(RoundRobinModel.COUNT_FILE, "wb") as f:
                next = (count +1) % self.modelcount
                f.write(next.to_bytes(2, 'little')) 
        except:
            self.logger_.error("", exc_info=True)

        self.lock.release()
        return count


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=' %(levelname)s - %(message)s')
    config = {
    }

    model = RoundRobinModel(config)
    for i in range(10):
        print(model.get_current_model())

