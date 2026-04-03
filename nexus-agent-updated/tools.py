import requests
import os
import subprocess
import json
import re

# Safe Wikipedia import
try:
    import wikipedia
    WIKI_AVAILABLE = True
except ImportError:
    WIKI_AVAILABLE = False

# Safe DuckDuckGo import
try:
    from duckduckgo_search import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False

# ================================================================
# TOOL 1 — Real Web Search
# ================================================================
def web_search(query: str) -> str:
    if not DDG_AVAILABLE:
        return "Web search not available. Install duckduckgo-search."
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query.strip(), max_results=6))
        if not results:
            return "No results found for that query."
        output = f"Web search results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
            output += f"{i}. {r.get('title','No title')}\n"
            output += f"   {r.get('body','No description')[:200]}\n"
            output += f"   URL: {r.get('href','')}\n\n"
        return output
    except Exception as e:
        return f"Search failed: {str(e)}"

# ================================================================
# TOOL 2 — Wikipedia
# ================================================================
def wikipedia_lookup(topic: str) -> str:
    if not WIKI_AVAILABLE:
        return "Wikipedia module not available."
    try:
        summary = wikipedia.summary(topic.strip(), sentences=6, auto_suggest=True)
        page = wikipedia.page(topic.strip(), auto_suggest=True)
        return f"Wikipedia — {page.title}:\n\n{summary}\n\nSource: {page.url}"
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            summary = wikipedia.summary(e.options[0], sentences=5)
            return f"Wikipedia (showing: {e.options[0]}):\n\n{summary}"
        except:
            return f"Ambiguous topic. Try being more specific. Options: {', '.join(e.options[:5])}"
    except Exception as e:
        return f"Wikipedia lookup failed: {str(e)}"

# ================================================================
# TOOL 3 — Real News
# ================================================================
def get_news(topic: str) -> str:
    try:
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key or api_key == "your_newsapi_key_here":
            # Fallback: use web search for news
            return web_search(f"latest news {topic} 2025")
        url = f"https://newsapi.org/v2/everything"
        params = {
            "q": topic.strip(),
            "pageSize": 6,
            "sortBy": "publishedAt",
            "apiKey": api_key,
            "language": "en"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("status") != "ok":
            return web_search(f"latest news {topic}")
        articles = data.get("articles", [])
        if not articles:
            return f"No news articles found for '{topic}'."
        output = f"Latest news about '{topic}':\n\n"
        for i, a in enumerate(articles, 1):
            output += f"{i}. {a.get('title','')}\n"
            output += f"   Source: {a.get('source',{}).get('name','Unknown')}\n"
            output += f"   {a.get('description','No description')[:150]}\n"
            output += f"   Published: {a.get('publishedAt','')[:10]}\n\n"
        return output
    except Exception as e:
        return f"News fetch failed: {str(e)}"

# ================================================================
# TOOL 4 — Run Python Code (Agent executes real code!)
# ================================================================
def run_python_code(code: str) -> str:
    try:
        # Clean code
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        # Write to temp file
        temp_file = "agent_outputs/_temp_exec.py"
        os.makedirs("agent_outputs", exist_ok=True)
        with open(temp_file, "w") as f:
            f.write(code)

        result = subprocess.run(
            ["python", temp_file],
            capture_output=True, text=True, timeout=15
        )

        try:
            os.remove(temp_file)
        except:
            pass

        output = result.stdout.strip()
        errors = result.stderr.strip()

        if errors and not output:
            return f"Code error:\n{errors}"
        if output:
            return f"Code executed successfully:\n{output}"
        return "Code ran with no output."
    except subprocess.TimeoutExpired:
        return "Code execution timed out (15 second limit)."
    except Exception as e:
        return f"Code execution failed: {str(e)}"

# ================================================================
# TOOL 5 — Calculator
# ================================================================
def calculate(expression: str) -> str:
    try:
        expression = expression.strip()
        import math
        safe_env = {
            '__builtins__': None,
            'abs': abs, 'round': round, 'min': min, 'max': max,
            'sum': sum, 'pow': pow, 'sqrt': math.sqrt,
            'pi': math.pi, 'e': math.e, 'log': math.log,
            'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
            'floor': math.floor, 'ceil': math.ceil
        }
        result = eval(expression, safe_env)
        return f"Result: {expression} = {result}"
    except Exception as e:
        return f"Math error: {str(e)}"

# ================================================================
# TOOL 6 — Weather (Free, no API key needed)
# ================================================================
def get_weather(city: str) -> str:
    try:
        city = city.strip()
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=8)
        data = response.json()
        current = data['current_condition'][0]
        weather = data['weather'][0]
        area = data['nearest_area'][0]

        location = area['areaName'][0]['value'] + ', ' + area['country'][0]['value']
        temp_c = current['temp_C']
        temp_f = current['temp_F']
        feels_c = current['FeelsLikeC']
        desc = current['weatherDesc'][0]['value']
        humidity = current['humidity']
        wind_kmph = current['windspeedKmph']
        max_c = weather['maxtempC']
        min_c = weather['mintempC']

        return (f"Weather in {location}:\n"
                f"Condition: {desc}\n"
                f"Temperature: {temp_c}°C / {temp_f}°F (Feels like {feels_c}°C)\n"
                f"Today's Range: {min_c}°C - {max_c}°C\n"
                f"Humidity: {humidity}%\n"
                f"Wind: {wind_kmph} km/h")
    except Exception as e:
        try:
            # Fallback to simple format
            url = f"https://wttr.in/{city.strip()}?format=3"
            r = requests.get(url, timeout=5)
            return r.text
        except:
            return f"Weather unavailable: {str(e)}"

# ================================================================
# TOOL 7 — Write File
# ================================================================
def write_file(input_str: str) -> str:
    try:
        os.makedirs("agent_outputs", exist_ok=True)
        if "|||" in input_str:
            parts = input_str.split("|||", 1)
            filename = parts[0].strip().replace("/", "_").replace("\\", "_")
            content = parts[1].strip()
        else:
            filename = "agent_output.txt"
            content = input_str
        path = f"agent_outputs/{filename}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File '{filename}' created successfully at {path}"
    except Exception as e:
        return f"File write failed: {str(e)}"

# ================================================================
# TOOL 8 — Read File
# ================================================================
def read_file(filename: str) -> str:
    try:
        filename = filename.strip().replace("/", "_").replace("\\", "_")
        path = f"agent_outputs/{filename}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"Contents of '{filename}':\n\n{content}"
    except FileNotFoundError:
        return f"File '{filename}' not found."
    except Exception as e:
        return f"File read failed: {str(e)}"

# ================================================================
# TOOL 9 — Summarize URL Content
# ================================================================
def fetch_url(url: str) -> str:
    try:
        url = url.strip()
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; NexusAgent/1.0)'}
        response = requests.get(url, headers=headers, timeout=10)
        text = response.text
        # Strip HTML tags roughly
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return f"Content from {url}:\n\n{clean[:2000]}..."
    except Exception as e:
        return f"URL fetch failed: {str(e)}"

# ================================================================
# TOOL REGISTRY
# ================================================================
TOOL_REGISTRY = {
    "web_search": {
        "function": web_search,
        "description": "Search the internet for real-time information on any topic",
        "usage": "web_search: your search query here",
        "icon": "🔍"
    },
    "wikipedia": {
        "function": wikipedia_lookup,
        "description": "Look up detailed, factual information from Wikipedia",
        "usage": "wikipedia: topic name",
        "icon": "📚"
    },
    "news": {
        "function": get_news,
        "description": "Get the latest real news articles on any topic",
        "usage": "news: topic",
        "icon": "📰"
    },
    "run_code": {
        "function": run_python_code,
        "description": "Write and execute Python code to solve computational problems",
        "usage": "run_code: print('hello')",
        "icon": "⚡"
    },
    "calculate": {
        "function": calculate,
        "description": "Perform mathematical calculations including advanced math",
        "usage": "calculate: 25 * 4 + sqrt(144)",
        "icon": "🔢"
    },
    "weather": {
        "function": get_weather,
        "description": "Get current weather conditions for any city worldwide",
        "usage": "weather: Jaipur",
        "icon": "🌤"
    },
    "write_file": {
        "function": write_file,
        "description": "Save content to a file on the server",
        "usage": "write_file: report.txt ||| content here",
        "icon": "💾"
    },
    "read_file": {
        "function": read_file,
        "description": "Read the contents of a previously created file",
        "usage": "read_file: report.txt",
        "icon": "📄"
    },
    "fetch_url": {
        "function": fetch_url,
        "description": "Fetch and read content from any website URL",
        "usage": "fetch_url: https://example.com",
        "icon": "🌐"
    }
}
