import re
import requests
import telebot
from telebot import types
from bs4 import BeautifulSoup
from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

TOKEN = "8911024888:AAFwQA3xp_uVWZjItENra0CykfvGnohTZU8"

bot = telebot.TeleBot(TOKEN)
URL = "https://books.toscrape.com/"
STARS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

Base = declarative_base()


class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True)
    title = Column(String, unique=True, nullable=False)
    price = Column(Float)
    rating = Column(String)


engine = create_engine("sqlite:///books.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def scrape_books():
    r = requests.get(URL, timeout=10)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    books = []
    for item in soup.find_all("article", class_="product_pod"):
        title = item.h3.a["title"]
        price = float(re.sub(r"[^\d.]", "", item.find("p", class_="price_color").text))
        rating = item.find("p", class_="star-rating")["class"][1]
        books.append((title, price, rating))
    return books


def save_books(books):
    new_count = 0
    with Session() as s:
        for title, price, rating in books:
            if s.query(Book).filter_by(title=title).first() is None:
                s.add(Book(title=title, price=price, rating=rating))
                new_count += 1
        s.commit()
    return new_count


def main_menu():
    m = types.InlineKeyboardMarkup()
    m.add(
        types.InlineKeyboardButton("📚 List", callback_data="list"),
        types.InlineKeyboardButton("🔍 Search", callback_data="search"),
    )
    return m


def books_markup(books):
    m = types.InlineKeyboardMarkup()
    for b in books:
        m.add(types.InlineKeyboardButton(
            f"{b.title[:40]} | {b.price}", callback_data=f"book_{b.id}"))
    m.add(types.InlineKeyboardButton(" منو", callback_data="menu"))
    return m


def do_list(chat_id):
    new = save_books(scrape_books())
    with Session() as s:
        books = s.query(Book).all()
        bot.send_message(chat_id, f" {new} کتاب جدید ذخیره شد.\nکل کتاب‌ها: {len(books)}",
                         reply_markup=books_markup(books))


def ask_search(chat_id):
    msg = bot.send_message(chat_id, " اسم کتاب را بنویس:")
    bot.register_next_step_handler(msg, do_search)


def do_search(message):
    query = (message.text or "").strip()
    with Session() as s:
        books = s.query(Book).filter(Book.title.ilike(f"%{query}%")).all()
        if not books:
            bot.send_message(message.chat.id, " چیزی پیدا نشد.", reply_markup=main_menu())
        else:
            bot.send_message(message.chat.id, f" {len(books)} نتیجه:",
                             reply_markup=books_markup(books))


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "یکی را انتخاب کن ", reply_markup=main_menu())


@bot.message_handler(commands=["list"])
def list_cmd(message):
    do_list(message.chat.id)


@bot.message_handler(commands=["search"])
def search_cmd(message):
    ask_search(message.chat.id)


@bot.callback_query_handler(func=lambda c: True)
def on_click(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if call.data == "list":
        do_list(chat_id)
    elif call.data == "search":
        ask_search(chat_id)
    elif call.data == "menu":
        bot.send_message(chat_id, "یکی را انتخاب کن ", reply_markup=main_menu())
    elif call.data.startswith("book_"):
        with Session() as s:
            b = s.get(Book, int(call.data.split("_")[1]))
            if b:
                text = (f" {b.title}\n"
                        f" قیمت: £{b.price}\n"
                        f" امتیاز: { STARS.get(b.rating, 0)} ({b.rating})")
                m = types.InlineKeyboardMarkup()
                m.add(types.InlineKeyboardButton(" منو", callback_data="menu"))
                bot.send_message(chat_id, text, reply_markup=m)

bot.infinity_polling()