from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import yt_dlp as ytdl

def clean_url(original_url):
    parsed = urlparse(original_url)
    query = parse_qs(parsed.query)
    
    # Keep only the video ID (v=)
    clean_query = {}
    if 'v' in query:
        clean_query['v'] = query['v']

    # Rebuild the cleaned URL
    new_query = urlencode(clean_query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=new_query))
    return cleaned_url


raw_url = "https://www.youtube.com/watch?v=U4hjdq3Tsc8&list=RDyUVVCRiymEk&index=22"
cleaned = clean_url(raw_url)
print(cleaned)

url = cleaned
info = ytdl.YoutubeDL().extract_info(url, download=False)
print(info)