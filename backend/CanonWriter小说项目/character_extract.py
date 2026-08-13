import json
import re


def extract_characters():

    try:

        with open(
            "user_chunks.json",
            "r",
            encoding="utf-8"
        ) as f:

            chunks = json.load(f)


    except:

        return [
            "林黛玉",
            "贾宝玉",
            "薛宝钗",
            "王熙凤"
        ]


    text = "\n".join(chunks)


    characters = []


    # 查找：
    # 角色：
    # 人物：
    pattern = r"(角色|人物)[：:]\s*([^\n]+)"


    result = re.findall(
        pattern,
        text
    )


    for item in result:

        name = item[1].strip()

        characters.append(
            name
        )


    if characters:

        return characters


    else:

        return [
            "未知角色"
        ]