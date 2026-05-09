
import pandas as pd

input_path = r"mapa.xlsx"
output_path  = "map040526.csv"
aba          = 0  # índice (0 = primeira) ou nome da aba, ex: "Planilha1"

df = pd.read_excel(input_path, sheet_name=aba, header=0)
df = df.convert_dtypes()
df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
print(f"Entrada : {input_path}")
print(f"Saída   : {output_path}")