#/bin/bash
source ./bin/activate

rm casambi.log*
python3 -m src.aiocasambi.__main__
