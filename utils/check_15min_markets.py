#!/usr/bin/env python3
"""Check order books for 15-minute crypto markets."""

import requests

def main():
    # Markets that returned 200 from CLOB
    cids = [
        ("Solana 4:30PM-4:45PM ET", "0xb7ecce63594d1e303355a69a289302cbaca4edf7a0f0e8f8bb74c4cc238ea652"),
        ("Ethereum 4:30PM-4:45PM ET", "0x901c7c937ae4c79aea52373a176b9a18b2337cec47b20f223b3e47cffe413a0f"),
        ("Bitcoin 4:30PM-4:45PM ET", "0xf3f5323b631c805de3a998e98340a66015380b875ba45d37c9ef7ee988746875"),
        ("XRP 4:30PM-4:45PM ET", "0xb5fdeca563bbe45b799f25a0c4e3dff6ec50ba1e80df6dd9135659e2b87fcbf6"),
    ]

    for name, cid in cids:
        print(f"{name}")

        # Get market
        resp = requests.get(f"https://clob.polymarket.com/markets/{cid}", timeout=10)
        if resp.status_code != 200:
            print(f"  Error: {resp.status_code}")
            continue

        data = resp.json()
        tokens = data.get("tokens", [])
        maker_fee = data.get("maker_base_fee", 0)
        taker_fee = data.get("taker_base_fee", 0)

        print(f"  Tokens: {len(tokens)}")
        print(f"  Fees: maker={maker_fee}%, taker={taker_fee}%")

        for t in tokens:
            token_id = t.get("token_id")
            outcome = t.get("outcome")

            # Get book
            book_resp = requests.get("https://clob.polymarket.com/book", params={"token_id": token_id}, timeout=10)
            if book_resp.status_code != 200:
                print(f"  {outcome}: Book error {book_resp.status_code}")
                continue

            book = book_resp.json()
            bids = book.get("bids", [])
            asks = book.get("asks", [])

            if bids and asks:
                best_bid = float(bids[0]["price"])
                best_ask = float(asks[0]["price"])
                spread = (best_ask - best_bid) * 100
                print(f"  {outcome}: Bid {best_bid:.3f} | Ask {best_ask:.3f} | Spread {spread:.1f}%")
                print(f"    Depth: {len(bids)} bids, {len(asks)} asks")
                if bids:
                    print(f"    Top bids: {bids[:3]}")
                if asks:
                    print(f"    Top asks: {asks[:3]}")
            else:
                print(f"  {outcome}: No bids ({len(bids)}) or asks ({len(asks)})")

        print()

if __name__ == "__main__":
    main()
