class CaseNewsDetailFormatter:
    @staticmethod
    def format(news):
        return {
            "img_url": news.img_url,
            "url": news.url,
            "date": news.date_published.strftime("%d %b %Y"),
            "title": news.title,
            "domain": CaseNewsDetailFormatter._extract_domain(news.url),
            "content": news.content
        }

    @staticmethod
    def _extract_domain(url):
        try:
            return url.split("/")[2] if url else ""
        except (IndexError, AttributeError):
            return ""

class CaseHealthProtocolDetailFormatter:
    @staticmethod
    def format(protocol):
        return {
            "title": protocol.title,
            "url": protocol.url
        }

class CaseGenderDetailFormatter:
    _gender_map = {
        "Male": "Pria",
        "Female": "Perempuan"
    }

    @staticmethod
    def format(gender):
        return CaseGenderDetailFormatter._gender_map.get(gender, gender) 