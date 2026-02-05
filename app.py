"""
=============================================================================
🎰 تطبيق اليانصيب الأردني - Golden Edition v5.0
=============================================================================
المطور: محمد العمري & Gemini AI
التاريخ: فبراير 2026

الميزات المدمجة:
- محرك Numpy فائق السرعة.
- فلاتر دقيقة (ظلال، فردي/زوجي، متتاليات، أحجام مختلفة).
- تصدير PDF احترافي.
- نظام المحفظة.
- فاحص التذاكر.
- واجهة مستخدم محسنة.
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import random
import io
import os
import requests
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple, Set, Union
from itertools import chain, combinations
from scipy.stats import poisson, hypergeom

# Visualization & Reporting
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from openpyxl import Workbook

import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

class LotteryConfig:
    MIN_NUM = 1
    MAX_NUM = 32
    # Data Source
    GITHUB_DATA_URL = "https://raw.githubusercontent.com/MohamedOmariJo/omari/main/250.xlsx"
    # Economics
    TICKET_PRICES = {6: 1, 7: 7, 8: 28, 9: 84, 10: 210}

# ==============================================================================
# 2. HELPER CLASSES (PDF, DATA)
# ==============================================================================

class PDFGenerator:
    @staticmethod
    def create_ticket_pdf(tickets: List[List[int]], draw_date: str = None) -> io.BytesIO:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(colors.darkblue)
        c.drawString(2 * cm, height - 3 * cm, "Jordan Lottery - Golden Ticket")
        
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.black)
        c.drawString(2 * cm, height - 4 * cm, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        y_pos = height - 6 * cm
        for i, ticket in enumerate(tickets, 1):
            if y_pos < 4 * cm:
                c.showPage()
                y_pos = height - 4 * cm
            
            c.setStrokeColor(colors.grey)
            c.rect(2 * cm, y_pos - 1.5 * cm, 17 * cm, 2 * cm, fill=0)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2.5 * cm, y_pos - 0.8 * cm, f"#{i}")
            
            x_ball = 4.5 * cm
            for num in ticket:
                c.setFillColor(colors.lightgrey)
                c.circle(x_ball + 0.5*cm, y_pos - 0.5*cm, 0.6*cm, fill=1, stroke=0)
                c.setFillColor(colors.black)
                c.drawCentredString(x_ball + 0.5*cm, y_pos - 0.65*cm, str(num))
                x_ball += 1.5 * cm
            
            y_pos -= 2.5 * cm
            
        c.save()
        buffer.seek(0)
        return buffer

class DataLoader:
    @staticmethod
    def load_from_github() -> Tuple[Optional[pd.DataFrame], str]:
        try:
            response = requests.get(LotteryConfig.GITHUB_DATA_URL, timeout=10)
            response.raise_for_status()
            df = pd.read_excel(io.BytesIO(response.content))
            return DataLoader._process(df)
        except Exception as e:
            return None, str(e)

    @staticmethod
    def load_from_file(file) -> Tuple[Optional[pd.DataFrame], str]:
        try:
            df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            return DataLoader._process(df)
        except Exception as e:
            return None, str(e)

    @staticmethod
    def _process(df: pd.DataFrame):
        cols = ['N1','N2','N3','N4','N5','N6']
        if not set(cols).issubset(df.columns): return None, "Format Error"
        
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        df.dropna(subset=cols, inplace=True)
        df['numbers'] = df[cols].values.tolist()
        df['numbers'] = df['numbers'].apply(lambda x: sorted([int(n) for n in x if 1<=n<=32]))
        df = df[df['numbers'].apply(len) == 6]
        
        # Stats
        df['sum'] = df['numbers'].apply(sum)
        return df, "Loaded"

# ==============================================================================
# 3. CORE LOGIC (Analyzer & Generator)
# ==============================================================================

class AdvancedAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.total = len(df)
        all_nums = list(chain.from_iterable(df['numbers']))
        self.freq = Counter(all_nums)
        self.hot = set(n for n, c in self.freq.most_common(12))
        self.cold = set(n for n, c in self.freq.most_common()[:-13:-1])
        
        # Gaps & Poisson
        self.gaps = {}
        for n in range(1, 33):
            locs = [i for i, nums in enumerate(df['numbers']) if n in nums]
            if locs:
                last_seen = self.total - 1 - locs[-1]
                prob = poisson.pmf(len(locs), (len(locs)/self.total)*self.total)
            else:
                last_seen = self.total
                prob = 0
            self.gaps[n] = {'last': last_seen, 'prob': prob}

    def get_stats(self, ticket):
        return {
            'sum': sum(ticket),
            'odd': sum(1 for n in ticket if n%2),
            'even': sum(1 for n in ticket if not n%2),
            'shadows': sum(1 for c in Counter([n%10 for n in ticket]).values() if c>1),
            'consec': sum(1 for i in range(len(ticket)-1) if ticket[i+1]-ticket[i]==1)
        }

class SmartGenerator:
    def __init__(self, analyzer: AdvancedAnalyzer):
        self.analyzer = analyzer

    def generate_batch(self, count, size, constraints):
        """
        توليد ذكي باستخدام الفلترة اللاحقة (Generate & Filter)
        لضمان السرعة مع الدقة في تلبية الشروط
        """
        valid_tickets = []
        batch_size = 50000  # Generate massive amount
        attempts = 0
        
        pool = list(range(1, 33))
        
        while len(valid_tickets) < count and attempts < 20:
            attempts += 1
            # 1. Fast Numpy Generation
            raw_data = np.random.choice(pool, size=(batch_size, size))
            raw_data.sort(axis=1)
            
            # Remove duplicates inside tickets (simple loop for cleanup, hard to vectorize perfectly with choice)
            # A faster way is using searchsorted or just filtering bad rows
            unique_mask = np.array([len(set(row)) == size for row in raw_data])
            candidates = raw_data[unique_mask]
            
            # 2. Apply Filters Vectorized-ish
            keep_mask = np.ones(len(candidates), dtype=bool)
            
            # Fixed Numbers Filter
            if constraints.get('fixed'):
                fixed_set = set(constraints['fixed'])
                # Check if fixed numbers are subset
                fixed_mask = np.array([fixed_set.issubset(set(row)) for row in candidates])
                keep_mask &= fixed_mask
            
            # Apply strict filters iteratively on remaining candidates
            current_candidates = candidates[keep_mask]
            final_batch = []
            
            last_draw_set = set(self.analyzer.df.iloc[-1]['numbers']) if constraints.get('last_draw_match') is not None else None
            
            for row in current_candidates:
                if len(final_batch) + len(valid_tickets) >= count: break
                
                # Odd/Even
                if constraints.get('odd_count') is not None:
                    odd = sum(1 for x in row if x%2)
                    if odd != constraints['odd_count']: continue
                
                # Shadows
                if constraints.get('shadow_count') is not None:
                    sh = sum(1 for c in Counter([x%10 for x in row]).values() if c>1)
                    if sh != constraints['shadow_count']: continue

                # Consecutive
                if constraints.get('consec_count') is not None:
                    cons = sum(1 for i in range(len(row)-1) if row[i+1]-row[i]==1)
                    if cons != constraints['consec_count']: continue

                # Last Draw Match
                if last_draw_set and constraints.get('last_draw_match') is not None:
                    match = len(set(row) & last_draw_set)
                    if match != constraints['last_draw_match']: continue
                
                final_batch.append(sorted(row.tolist()))
            
            valid_tickets.extend(final_batch)
        
        return valid_tickets[:count]

# ==============================================================================
# 4. UI COMPONENTS
# ==============================================================================

def init_app():
    st.set_page_config(page_title="Jordan Lottery Golden v5.0", layout="wide", page_icon="🎰")
    if 'portfolio' not in st.session_state: st.session_state.portfolio = []
    
    st.markdown("""
    <style>
        .stButton>button {width: 100%; border-radius: 8px;}
        .ball {display:inline-block; width:35px; height:35px; line-height:35px; 
               text-align:center; border-radius:50%; color:white; font-weight:bold; margin:2px;}
        .hot {background:#ef4444;} .cold {background:#3b82f6;} .neutral {background:#10b981;}
        .stat-box {background:#262730; padding:10px; border-radius:5px; text-align:center;}
    </style>
    """, unsafe_allow_html=True)

def render_ball(num, analyzer):
    cls = "hot" if num in analyzer.hot else ("cold" if num in analyzer.cold else "neutral")
    return f'<div class="ball {cls}">{num}</div>'

def main():
    init_app()
    
    # Sidebar
    with st.sidebar:
        st.title("Golden Edition v5.0")
        if st.button("🔄 تحميل البيانات (GitHub)"):
            df, msg = DataLoader.load_from_github()
            if df is not None:
                st.session_state.df = df
                st.session_state.analyzer = AdvancedAnalyzer(df)
                st.success(msg)
    
    if 'df' not in st.session_state:
        st.warning("الرجاء تحميل البيانات من القائمة الجانبية")
        return

    analyzer = st.session_state.analyzer
    gen = SmartGenerator(analyzer)
    
    tabs = st.tabs(["🎰 المولد المتقدم", "🔍 الفاحص", "💼 محفظتي", "📊 التحليل"])
    
    # --- TAB 1: GENERATOR ---
    with tabs[0]:
        col_param, col_res = st.columns([1, 2])
        
        with col_param:
            st.subheader("إعدادات التوليد")
            with st.form("gen_form"):
                size = st.slider("حجم التذكرة", 6, 10, 6)
                count = st.slider("عدد التذاكر", 1, 20, 5)
                
                st.markdown("---")
                st.markdown("**القيود الدقيقة (اختياري)**")
                
                c1, c2 = st.columns(2)
                with c1:
                    fixed_str = st.text_input("تثبيت أرقام (مثال: 5,10)")
                    odd_req = st.selectbox("عدد الفردي", ["عشوائي"] + list(range(size+1)))
                    shadow_req = st.selectbox("عدد الظلال", ["عشوائي"] + list(range(4)))
                with c2:
                    consec_req = st.selectbox("عدد المتتاليات", ["عشوائي"] + list(range(4)))
                    match_last = st.selectbox("من آخر سحب", ["عشوائي"] + list(range(5)))

                submit = st.form_submit_button("🚀 توليد الآن")
        
        if submit:
            constraints = {}
            if fixed_str: constraints['fixed'] = [int(x) for x in fixed_str.split(',')]
            if odd_req != "عشوائي": constraints['odd_count'] = int(odd_req)
            if shadow_req != "عشوائي": constraints['shadow_count'] = int(shadow_req)
            if consec_req != "عشوائي": constraints['consec_count'] = int(consec_req)
            if match_last != "عشوائي": constraints['last_draw_match'] = int(match_last)
            
            with st.spinner("جاري التوليد والفلترة..."):
                tickets = gen.generate_batch(count, size, constraints)
                st.session_state.generated = tickets
                if len(tickets) < count:
                    st.warning(f"تم العثور على {len(tickets)} تذكرة فقط تطابق الشروط الصارمة.")

        with col_res:
            if 'generated' in st.session_state and st.session_state.generated:
                st.subheader("التذاكر المولدة")
                
                # PDF Export
                pdf = PDFGenerator.create_ticket_pdf(st.session_state.generated)
                st.download_button("📄 تحميل PDF", pdf, "tickets.pdf", "application/pdf")
                
                for i, t in enumerate(st.session_state.generated):
                    stats = analyzer.get_stats(t)
                    with st.expander(f"تذكرة #{i+1} | {t}", expanded=True):
                        st.markdown(" ".join([render_ball(n, analyzer) for n in t]), unsafe_allow_html=True)
                        st.caption(f"مجموع: {stats['sum']} | فردي: {stats['odd']} | ظلال: {stats['shadows']} | متتاليات: {stats['consec']}")
                        if st.button(f"💾 حفظ #{i+1}", key=f"s_{i}"):
                            if t not in st.session_state.portfolio:
                                st.session_state.portfolio.append(t)
                                st.toast("تم الحفظ!")

    # --- TAB 2: CHECKER ---
    with tabs[1]:
        st.header("فاحص التذاكر")
        check_input = st.text_input("أدخل أرقامك (مفصولة بفواصل)", "5, 12, 18, 23, 27, 31")
        if check_input:
            try:
                ticket = sorted([int(x) for x in check_input.split(',')])
                st.markdown(" ".join([render_ball(n, analyzer) for n in ticket]), unsafe_allow_html=True)
                
                stats = analyzer.get_stats(ticket)
                c1, c2, c3 = st.columns(3)
                c1.metric("المجموع", stats['sum'])
                c2.metric("فردي/زوجي", f"{stats['odd']}/{stats['even']}")
                c3.metric("الظلال", stats['shadows'])
                
                st.subheader("المطابقة التاريخية")
                matches = []
                for idx, row in st.session_state.df.iterrows():
                    m = len(set(ticket) & set(row['numbers']))
                    if m >= 3:
                        matches.append((row['draw_id'], m, row['numbers']))
                
                if matches:
                    matches.sort(key=lambda x: x[1], reverse=True)
                    for draw_id, count, nums in matches[:5]:
                        st.write(f"سحب #{draw_id}: {count} تطابقات {list(set(ticket)&set(nums))}")
                else:
                    st.info("لم تربح هذه الأرقام جائزة (3+) سابقاً")
                    
            except:
                st.error("تنسيق غير صحيح")

    # --- TAB 3: PORTFOLIO ---
    with tabs[2]:
        st.header("محفظتي")
        if not st.session_state.portfolio:
            st.info("المحفظة فارغة")
        else:
            last_draw = set(st.session_state.df.iloc[-1]['numbers'])
            for idx, t in enumerate(st.session_state.portfolio):
                matches = len(set(t) & last_draw)
                color = "#d1fae5" if matches >=3 else "#f3f4f6"
                st.markdown(f"""
                <div style="background:{color}; padding:10px; border-radius:5px; margin:5px; color:black;">
                    <b>#{idx+1}:</b> {t} <br>
                    تطابق مع آخر سحب: <b>{matches}</b>
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("مسح المحفظة"):
                st.session_state.portfolio = []
                st.rerun()

    # --- TAB 4: ANALYTICS ---
    with tabs[3]:
        st.header("التحليلات المتقدمة")
        
        # Poisson
        st.subheader("شذوذ التكرار (Poisson)")
        p_data = [{'Num':k, 'Score':1-v['prob'], 'Freq':analyzer.freq[k]} for k,v in analyzer.gaps.items()]
        fig = px.scatter(p_data, x='Num', y='Score', size='Freq', color='Score', title="مؤشر الشذوذ الاحتمالي")
        st.plotly_chart(fig, use_container_width=True)
        
        # Prediction (Gaps & Next)
        st.subheader("الفجوات الزمنية")
        gaps_df = pd.DataFrame([{'Num':k, 'LastSeen':v['last']} for k,v in analyzer.gaps.items()])
        fig2 = px.bar(gaps_df, x='Num', y='LastSeen', title="عدد السحوبات منذ آخر ظهور")
        st.plotly_chart(fig2, use_container_width=True)

if __name__ == "__main__":
    main()
