# Kaktus Dobíječka extractor

This repository contains a "quick & dirty" Python script, 
[`kaktus_dobijecka_extractor.py`](kaktus_dobijecka_extractor.py), for extracting information about announcements of
**Dobíječka**, a happy hour event organized by [**Kaktus**](https://www.mujkaktus.cz/homepage), a Czech MVNO, during 
which one can get their prepaid credit recharges doubled.

The script extracts the announcements from multiple ["Novinky z květináče"](https://www.mujkaktus.cz/novinky) web pages 
(from the "live" one and from archived ones on 
[web.archive.org](https://web.archive.org/web/20200601000000*/https://www.mujkaktus.cz/novinky)) to get as much data as 
possible, and saves the following information into a **CSV** and a **JSON** file:
- `date`
- `hour_begin`
- `hour_end`
- `title`
- `description`



## Usage
```shell
cd kaktus-dobijecka-extractor
python3 -m venv __venv__
. __venv__/bin/activate
__venv__/bin/pip3 install -r requirements.txt
__venv__/bin/python3 kaktus_dobijecka_extractor.py
```

Tested on Debian 11 with **Python 3.9** installed.



## Licensing
This project is licensed under the **3-clause BSD license** – see the [LICENSE](LICENSE) file.

Programmed by **[Vít Labuda](https://vitlabuda.cz/)**.
