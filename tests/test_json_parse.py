import json

def test_json_parse():
    # Simulamos la respuesta que devuelve tu IA
    response_text = """
    El sistema ha clasificado el ticket como Petición (14).
    {"type_id": 14, "diagnostico": "Se ha clasificado como Petición (14). Se requiere contactar al usuario para clarificar la intención del ticket."}
    """

    print("=== TEXTO COMPLETO DE LA IA ===")
    print(response_text)

    # Extraemos el JSON de la respuesta
    """
    start = response_text.find("{")
    end = response_text.rfind("}")
    json_string = response_text[start:end + 1]
    """
    

    print("\n=== CADENA JSON EXTRAÍDA ===")
    print(json_string)

    try:
        parsed = json.loads(json_string)
        print("\n✅ JSON convertido correctamente:")
        print(parsed)
    except json.JSONDecodeError as e:
        print(f"\n❌ Error al convertir a JSON: {e}")

if __name__ == "__main__":
    test_json_parse()
