"""Landscape certificate PDF using Madar's existing Matplotlib/Arabic stack."""
import base64
import io
import threading
import textwrap
import matplotlib
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PIL import Image
import qrcode

_RENDER_LOCK = threading.Lock()  # Matplotlib's global font/cache internals are shared.


def render_certificate(data):
    with _RENDER_LOCK, matplotlib.rc_context({'pdf.fonttype': 42, 'font.family': 'DejaVu Sans', 'text.usetex': False}):
        # Pinned Matplotlib 3.11 shapes and reorders logical Unicode with libraqm.
        # Preprocessing with arabic_reshaper/python-bidi would reverse Arabic twice.
        fig = Figure(figsize=(11.6929, 8.2677), facecolor='#fffdf8')  # A4 landscape
        ax = fig.add_axes([0, 0, 1, 1]); ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
        for margin, weight in ((.04, 2), (.053, .7)):
            ax.add_patch(Rectangle((margin, margin), 1-2*margin, 1-2*margin, fill=False, linewidth=weight, edgecolor='#ad8b45'))

        def text(value, y, size=16, color='#243745', width=.84):
            artist = ax.text(.5, y, value, ha='center', va='center', fontsize=size, color=color, parse_math=False)
            # Fit real glyph widths rather than allowing long names/titles to clip.
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            canvas = FigureCanvasAgg(fig); canvas.draw()
            measured = artist.get_window_extent(canvas.get_renderer()).width
            allowed = fig.bbox.width * width
            if measured > allowed: artist.set_fontsize(max(7, size * allowed / measured))

        design = data['design']
        if design.get('logo_image'):
            image = Image.open(io.BytesIO(base64.b64decode(design['logo_image'])))
            logo = fig.add_axes([.41, .78, .18, .11]); logo.imshow(image); logo.axis('off')
        text(design['issuer_name'], .75, 13)
        text(design['title'], .66, 30)
        text(design.get('subtitle', ''), .59, 14)
        text(data['learner_name'], .50, 28)
        text(data['course_name'], .42, 19)
        lines = []
        for paragraph in design.get('body', '').splitlines(): lines.extend(textwrap.wrap(paragraph, width=110) or [''])
        # Template validation bounds input; font shrinks for unusually verbose designs.
        font = min(12, 140/max(len(lines), 1))
        for index, line in enumerate(lines): text(line, .36-index*.13/max(len(lines), 1), font)
        text('Completion / إتمام: ' + data['completion_date'] + '    ·    Issued / إصدار: ' + data['issue_date'], .19, 10, width=.68)
        text(data['credential_number'], .10, 9, width=.65)
        qr = qrcode.make(data['verification_url']).convert('RGB')
        qr_ax = fig.add_axes([.80, .075, .13, .17]); qr_ax.imshow(qr, interpolation='nearest'); qr_ax.axis('off')
        if design.get('signature_image'):
            sign = fig.add_axes([.08, .15, .16, .065]); sign.imshow(Image.open(io.BytesIO(base64.b64decode(design['signature_image'])))); sign.axis('off')
        ax.text(.16, .135, design.get('signer_name', ''), ha='center', fontsize=9, parse_math=False)
        ax.text(.16, .11, design.get('signer_title', ''), ha='center', fontsize=8, parse_math=False)
        if data['status'] == 'revoked': text('REVOKED / ملغاة', .94, 14, '#a22')
        target = io.BytesIO()
        fig.savefig(target, format='pdf', metadata={'Title': design['title'], 'Author': design['issuer_name'], 'CreationDate': None})
        fig.clear()
        return target.getvalue()
