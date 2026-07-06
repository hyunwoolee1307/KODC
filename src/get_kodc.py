import requests

base_url = "https://www.nifs.go.kr/OpenAPI_json?id=sooList"
key = "qPwOeIrU-2607-DNCWXA-1729"  # from 2026-07-06 to 2027-07-05

for year in range(1961, 2026):
    sdate = f"{year}0101"
    edate = f"{year}1231"
    url = base_url + f"&key={key}&sdate={sdate}&edate={edate}"
    response = requests.get(url)

    with open(f"kodc{year}.json", "wb") as file:
        file.write(response.content)
    print(f"kodc {year} download complete.")

