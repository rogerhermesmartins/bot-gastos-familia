import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = "8364558368:AAGkEskPWldVUe7fptk-JhsLcoLwYwe8Ke0"

CATEGORIAS = {
    "Alimentação": ["mercado", "supermercado", "padaria", "restaurante", "ifood", "pizza"],
    "Transporte": ["uber", "99", "gasolina", "combustível"],
    "Contas": ["luz", "água", "internet", "aluguel"],
    "Lazer": ["netflix", "cinema", "spotify"],
    "Saúde": ["farmácia", "remédio", "consulta"]
}

# ---------------- BANCO ----------------

def init_db():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS casas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            codigo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            nome TEXT,
            casa_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            casa_id INTEGER,
            user_id INTEGER,
            nome TEXT,
            categoria TEXT,
            valor REAL,
            data TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            casa_id INTEGER PRIMARY KEY,
            limite_mensal REAL
        )
    """)

    conn.commit()
    conn.close()

def salvar_gasto(casa_id, user_id, nome, categoria, valor):
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gastos (casa_id, user_id, nome, categoria, valor, data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (casa_id, user_id, nome, categoria, valor, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()


def obter_resumo_mes():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    mes_atual = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT nome, SUM(valor)
        FROM gastos
        WHERE data LIKE ?
        GROUP BY nome
    """, (f"{mes_atual}%",))
    dados = cursor.fetchall()
    conn.close()
    return dados

def obter_gastos_por_categoria():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    mes_atual = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT categoria, SUM(valor)
        FROM gastos
        WHERE data LIKE ?
        GROUP BY categoria
        ORDER BY SUM(valor) DESC
    """, (f"{mes_atual}%",))
    dados = cursor.fetchall()
    conn.close()
    return dados

def definir_limite(valor):
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM configuracoes")
    cursor.execute("INSERT INTO configuracoes (id, limite_mensal) VALUES (1, ?)", (valor,))
    conn.commit()
    conn.close()

def obter_limite():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute("SELECT limite_mensal FROM configuracoes WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def total_gasto_mes():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()

    inicio = datetime.now().strftime("%Y-%m-01")
    cursor.execute("""
        SELECT SUM(valor)
        FROM gastos
        WHERE date(substr(data, 1, 10)) >= date(?)
    """, (inicio,))

    total = cursor.fetchone()[0]
    conn.close()
    return total or 0

def gerar_alerta_limite(total, limite):
    restante = limite - total

    if total >= limite:
        return (
            f"🚨 *Limite mensal ultrapassado!*\n"
            f"💰 Total gasto: R$ {total:.2f}\n"
            f"📉 Limite: R$ {limite:.2f}"
        )

    if total >= limite * 0.8:
        return (
            f"⚠️ *Atenção ao limite mensal*\n"
            f"💰 Gasto atual: R$ {total:.2f}\n"
            f"📉 Limite: R$ {limite:.2f}\n"
            f"👉 Faltam R$ {restante:.2f}"
        )

    return None

def limpar_gastos():
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gastos")
    conn.commit()
    conn.close()

import random
import string

def criar_casa(nome):
    codigo = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO casas (nome, codigo) VALUES (?, ?)",
        (nome, codigo)
    )
    casa_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return casa_id, codigo

def salvar_usuario(user, casa_id):
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO usuarios (user_id, nome, casa_id)
        VALUES (?, ?, ?)
    """, (user.id, user.first_name, casa_id))
    conn.commit()
    conn.close()

def obter_casa_usuario(user_id):
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT casa_id FROM usuarios WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def entrar_casa(codigo):
    conn = sqlite3.connect("gastos.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM casas WHERE codigo = ?",
        (codigo,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None



# ---------------- LÓGICA ----------------

def identificar_categoria(texto):
    for categoria, palavras in CATEGORIAS.items():
        for palavra in palavras:
            if palavra in texto:
                return categoria
    return "Outros"

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bot de gastos iniciado!\n"
        "Exemplo: mercado 120"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    user = update.message.from_user

    try:
        partes = texto.split()
        valor = float(partes[-1].replace(",", "."))
        descricao = " ".join(partes[:-1])
        categoria = identificar_categoria(descricao)
        casa_id = obter_casa_usuario(user.id)
        if not casa_id:
            await update.message.reply_text(
                "🏠 Você ainda não faz parte de uma casa.\n"
                "Use /criar_casa ou /entrar"
            )
            return

        salvar_gasto(casa_id, user.id, user.first_name, categoria, valor)
       
        limite = obter_limite()
        total = total_gasto_mes()

        if limite:
            alerta = gerar_alerta_limite(total, limite)
            if alerta:
                await update.message.reply_text(alerta, parse_mode="Markdown")



        if limite:
            if total >= limite:
                await update.message.reply_text(
                    "🚨 Atenção! Limite mensal ultrapassado!"
                )
            elif total >= limite * 0.8:
                await update.message.reply_text(
                    "⚠️ Você já usou 80% do limite mensal."
                )

        await update.message.reply_text(
            f"✅ Gasto registrado!\n"
            f"👤 {user.first_name}\n"
            f"📂 {categoria}\n"
            f"📝 {descricao.title()}\n"
            f"💰 R$ {valor:.2f}"
        )

    except:
        await update.message.reply_text("❌ Use: mercado 120")
        

async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dados = obter_resumo_mes()

    if not dados:
        await update.message.reply_text("📭 Nenhum gasto este mês.")
        return

    msg = "📊 *Resumo do mês*\n\n"
    total = 0

    for nome, valor in dados:
        msg += f"👤 {nome}: R$ {valor:.2f}\n"
        total += valor

    msg += f"\n💰 *Total:* R$ {total:.2f}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dados = obter_gastos_por_categoria()

    if not dados:
        await update.message.reply_text("📭 Nenhum gasto este mês.")
        return

    total = sum(valor for _, valor in dados)
    msg = "📊 *Gastos por categoria*\n\n"

    for categoria, valor in dados:
        perc = (valor / total) * 100
        msg += f"📂 {categoria}: R$ {valor:.2f} ({perc:.1f}%)\n"

    msg += f"\n💰 *Total:* R$ {total:.2f}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def limite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(context.args[0].replace(",", "."))
        definir_limite(valor)
        await update.message.reply_text(
            f"✅ Limite mensal definido em R$ {valor:.2f}"
        )
    except:
        await update.message.reply_text("❌ Use: /limite 2000")

async def limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limpar_gastos()
    await update.message.reply_text(
        "🗑️ Todos os gastos foram apagados com sucesso."
    )

async def criar_casa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /criar_casa NomeDaCasa")
        return

    nome = " ".join(context.args)
    casa_id, codigo = criar_casa(nome)

    salvar_usuario(update.message.from_user, casa_id)

    await update.message.reply_text(
        f"🏠 Casa *{nome}* criada com sucesso!\n"
        f"🔑 Código de entrada: `{codigo}`",
        parse_mode="Markdown"
    )
async def entrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /entrar CODIGO")
        return

    codigo = context.args[0].upper()
    casa_id = entrar_casa(codigo)

    if not casa_id:
        await update.message.reply_text("❌ Código inválido.")
        return

    salvar_usuario(update.message.from_user, casa_id)
    await update.message.reply_text("✅ Você entrou na casa com sucesso!")



# ---------------- MAIN ----------------

if __name__ == "__main__":
    init_db()
    print("Bot rodando...")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resumo", resumo))
    app.add_handler(CommandHandler("categorias", categorias))
    app.add_handler(CommandHandler("limite", limite))
    app.add_handler(CommandHandler("limpar", limpar))
    app.add_handler(CommandHandler("criar_casa", criar_casa_cmd))
    app.add_handler(CommandHandler("entrar", entrar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
