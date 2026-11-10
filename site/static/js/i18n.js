/* Interface translation (menus, headings, buttons and labels) into Hindi, Spanish, French and Arabic.
   Data names, values and generated sentences stay in English. The choice is kept in localStorage;
   Arabic switches the page to right-to-left. Original English text is restored when switching back. */
(() => {
  const LANGS = { en: "English", hi: "हिन्दी", es: "Español", fr: "Français", ar: "العربية" };
  // English -> [Hindi, Spanish, French, Arabic]
  const T = {
    "World": ["विश्व", "Mundo", "Monde", "العالم"], "Countries": ["देश", "Países", "Pays", "الدول"], "Rankings": ["रैंकिंग", "Clasificaciones", "Classements", "التصنيفات"],
    "Markets": ["बाज़ार", "Mercados", "Marchés", "الأسواق"], "Geopolitics": ["भू-राजनीति", "Geopolítica", "Géopolitique", "الجغرافيا السياسية"],
    "Reports": ["रिपोर्ट", "Informes", "Rapports", "التقارير"], "Explore": ["खोजें", "Explorar", "Explorer", "استكشف"], "Lab": ["लैब", "Laboratorio", "Labo", "المختبر"],
    "Data & API": ["डेटा और API", "Datos y API", "Données et API", "البيانات وواجهة API"], "Methodology": ["कार्यप्रणाली", "Metodología", "Méthodologie", "المنهجية"],
    "Insights": ["विश्लेषण", "Análisis", "Analyses", "رؤى"], "About": ["परिचय", "Acerca de", "À propos", "حول"],
    "Overview": ["अवलोकन", "Resumen", "Vue d’ensemble", "نظرة عامة"], "Live news": ["ताज़ा समाचार", "Noticias en directo", "Actualités en direct", "أخبار مباشرة"],
    "Weekly briefing": ["साप्ताहिक ब्रीफ़िंग", "Resumen semanal", "Point hebdomadaire", "الموجز الأسبوعي"], "Crisis tracker": ["संकट ट्रैकर", "Seguimiento de crisis", "Suivi des crises", "متتبع الأزمات"],
    "Crises": ["संकट", "Crisis", "Crises", "الأزمات"], "Conflicts": ["संघर्ष", "Conflictos", "Conflits", "النزاعات"], "Risk index": ["जोखिम सूचकांक", "Índice de riesgo", "Indice de risque", "مؤشر المخاطر"],
    "Power index": ["शक्ति सूचकांक", "Índice de poder", "Indice de puissance", "مؤشر القوة"], "Power": ["शक्ति", "Poder", "Puissance", "القوة"],
    "Sanctions": ["प्रतिबंध", "Sanciones", "Sanctions", "العقوبات"], "UN alignment": ["संयुक्त राष्ट्र में रुख", "Alineamiento en la ONU", "Alignement à l’ONU", "التوافق في الأمم المتحدة"],
    "Displacement": ["विस्थापन", "Desplazamiento", "Déplacements", "النزوح"], "Blocs": ["गुट", "Bloques", "Blocs", "التكتلات"], "Defence": ["रक्षा", "Defensa", "Défense", "الدفاع"],
    "Relations": ["संबंध", "Relaciones", "Relations", "العلاقات"], "Watchlist": ["निगरानी सूची", "Seguimiento", "Liste de suivi", "قائمة المتابعة"],
    "Map explorer": ["मानचित्र", "Explorador de mapas", "Explorateur de carte", "مستكشف الخرائط"], "Timeline map": ["समयरेखा मानचित्र", "Mapa en el tiempo", "Carte chronologique", "خريطة زمنية"],
    "Where would I fit?": ["मैं कहाँ फिट होऊँगा?", "¿Dónde encajaría?", "Où serais-je à ma place ?", "أين سأنتمي؟"], "Topics": ["विषय", "Temas", "Thèmes", "المواضيع"],
    "Cities": ["शहर", "Ciudades", "Villes", "المدن"], "Universities": ["विश्वविद्यालय", "Universidades", "Universités", "الجامعات"], "Compare": ["तुलना करें", "Comparar", "Comparer", "قارن"],
    "Index Builder": ["सूचकांक निर्माता", "Creador de índices", "Créateur d’indice", "منشئ المؤشرات"], "The Lab": ["लैब", "El laboratorio", "Le labo", "المختبر"],
    "Data": ["डेटा", "Datos", "Données", "البيانات"], "Markets by industry": ["उद्योग के अनुसार बाज़ार", "Mercados por sector", "Marchés par secteur", "الأسواق حسب القطاع"],
    "Popular statistics": ["लोकप्रिय आँकड़े", "Estadísticas populares", "Statistiques populaires", "إحصاءات شائعة"],
    "View all markets →": ["सभी बाज़ार देखें →", "Ver todos los mercados →", "Voir tous les marchés →", "عرض كل الأسواق ←"],
    "All rankings →": ["सभी रैंकिंग →", "Todas las clasificaciones →", "Tous les classements →", "كل التصنيفات ←"],
    "Indicators": ["संकेतक", "Indicadores", "Indicateurs", "المؤشرات"], "Sources & licences": ["स्रोत और लाइसेंस", "Fuentes y licencias", "Sources et licences", "المصادر والتراخيص"],
    "Downloads": ["डाउनलोड", "Descargas", "Téléchargements", "التنزيلات"], "Open API": ["खुला API", "API abierta", "API ouverte", "واجهة API مفتوحة"],
    "Editorial policy": ["संपादकीय नीति", "Política editorial", "Politique éditoriale", "السياسة التحريرية"], "Errata": ["सुधार", "Erratas", "Errata", "تصويبات"],
    "Licences & citing": ["लाइसेंस और उद्धरण", "Licencias y citas", "Licences et citation", "التراخيص والاستشهاد"], "Funding": ["वित्तपोषण", "Financiación", "Financement", "التمويل"],
    "Privacy": ["गोपनीयता", "Privacidad", "Confidentialité", "الخصوصية"],
    "Featured rankings": ["चुनिंदा रैंकिंग", "Clasificaciones destacadas", "Classements à la une", "تصنيفات مختارة"], "How to read this site": ["इस साइट को कैसे पढ़ें", "Cómo leer este sitio", "Comment lire ce site", "كيف تقرأ هذا الموقع"],
    "At a glance": ["एक नज़र में", "De un vistazo", "En bref", "لمحة سريعة"], "Quick answers": ["त्वरित उत्तर", "Respuestas rápidas", "Réponses rapides", "إجابات سريعة"],
    "Trends": ["रुझान", "Tendencias", "Tendances", "الاتجاهات"], "Related": ["संबंधित", "Relacionado", "Voir aussi", "ذو صلة"], "History": ["इतिहास", "Historia", "Histoire", "التاريخ"],
    "Live geopolitical news": ["ताज़ा भू-राजनीतिक समाचार", "Noticias geopolíticas en directo", "Actualités géopolitiques en direct", "أخبار جيوسياسية مباشرة"],
    "All news →": ["सभी समाचार →", "Todas las noticias →", "Toutes les actualités →", "كل الأخبار ←"], "Key findings": ["मुख्य निष्कर्ष", "Conclusiones clave", "Principaux résultats", "أهم النتائج"],
    "In brief": ["संक्षेप में", "En resumen", "En bref", "باختصار"], "More reports": ["और रिपोर्ट", "Más informes", "Autres rapports", "المزيد من التقارير"],
    "Other markets": ["अन्य बाज़ार", "Otros mercados", "Autres marchés", "أسواق أخرى"], "All indicators": ["सभी संकेतक", "Todos los indicadores", "Tous les indicateurs", "كل المؤشرات"],
    "Rankings in this market": ["इस बाज़ार की रैंकिंग", "Clasificaciones de este mercado", "Classements de ce marché", "تصنيفات هذا السوق"],
    "Global trend reports": ["वैश्विक रुझान रिपोर्ट", "Informes de tendencias mundiales", "Rapports sur les tendances mondiales", "تقارير الاتجاهات العالمية"],
    "Regional reports": ["क्षेत्रीय रिपोर्ट", "Informes regionales", "Rapports régionaux", "تقارير إقليمية"], "Members": ["सदस्य", "Miembros", "Membres", "الأعضاء"],
    "Other blocs": ["अन्य गुट", "Otros bloques", "Autres blocs", "تكتلات أخرى"], "Other crises": ["अन्य संकट", "Otras crisis", "Autres crises", "أزمات أخرى"],
    "Treaties": ["संधियाँ", "Tratados", "Traités", "المعاهدات"], "Biggest rises": ["सबसे बड़ी वृद्धि", "Mayores subidas", "Plus fortes hausses", "أكبر الارتفاعات"],
    "Biggest falls": ["सबसे बड़ी गिरावट", "Mayores caídas", "Plus fortes baisses", "أكبر الانخفاضات"], "All countries": ["सभी देश", "Todos los países", "Tous les pays", "كل الدول"],
    "Live news about both": ["दोनों पर ताज़ा समाचार", "Noticias sobre ambos", "Actualités sur les deux", "أخبار عن البلدين"], "Featured relationships": ["चुनिंदा संबंध", "Relaciones destacadas", "Relations à la une", "علاقات مختارة"],
    "Download CSV": ["CSV डाउनलोड करें", "Descargar CSV", "Télécharger le CSV", "تنزيل CSV"], "Save as PDF": ["PDF सहेजें", "Guardar como PDF", "Enregistrer en PDF", "حفظ PDF"],
    "Build report": ["रिपोर्ट बनाएँ", "Crear informe", "Créer le rapport", "إنشاء التقرير"], "Build a country report": ["देश रिपोर्ट बनाएँ", "Crear un informe de país", "Créer un rapport pays", "إنشاء تقرير عن دولة"],
    "Copy link": ["लिंक कॉपी करें", "Copiar enlace", "Copier le lien", "نسخ الرابط"], "Embed": ["एम्बेड", "Insertar", "Intégrer", "تضمين"],
    "Embed this tracker": ["यह ट्रैकर एम्बेड करें", "Insertar este seguimiento", "Intégrer ce suivi", "تضمين هذا المتتبع"], "☆ Watch": ["☆ निगरानी", "☆ Seguir", "☆ Suivre", "☆ متابعة"],
    "★ Watching": ["★ निगरानी में", "★ Siguiendo", "★ Suivi", "★ قيد المتابعة"], "Add to watchlist": ["निगरानी सूची में जोड़ें", "Añadir a seguimiento", "Ajouter au suivi", "أضف إلى المتابعة"],
    "Country": ["देश", "País", "Pays", "الدولة"], "Search": ["खोजें", "Buscar", "Rechercher", "بحث"], "Indicator": ["संकेतक", "Indicador", "Indicateur", "المؤشر"],
    "Year": ["वर्ष", "Año", "Année", "السنة"], "Topics ": ["विषय", "Temas", "Thèmes", "المواضيع"], "Sources.": ["स्रोत।", "Fuentes.", "Sources.", "المصادر."],
    "Top stories": ["मुख्य समाचार", "Principales noticias", "À la une", "أهم الأخبار"], "War & conflict": ["युद्ध और संघर्ष", "Guerra y conflicto", "Guerre et conflits", "الحرب والنزاع"],
    "Diplomacy": ["कूटनीति", "Diplomacia", "Diplomatie", "الدبلوماسية"], "Sanctions & trade": ["प्रतिबंध और व्यापार", "Sanciones y comercio", "Sanctions et commerce", "العقوبات والتجارة"],
    "Elections & unrest": ["चुनाव और अशांति", "Elecciones y disturbios", "Élections et troubles", "الانتخابات والاضطرابات"], "Language": ["भाषा", "Idioma", "Langue", "اللغة"],
  };
  const IDX = { hi: 0, es: 1, fr: 2, ar: 3 };
  const SEL = "header.top a, header.top summary, .utility a, .nav-panel a, .nav-panel h4, .nav-extra a, footer.site h4, footer.site a, " +
              ".section-head h2, .section-head a, .geo-nav a, .lab-nav a, .btn, button, label > span, legend, .gd-tabs button, .rp-summary h2, " +
              ".card h3, th, .mk-others a, .geo-src b";
  const KEY = "atg-lang";
  const get = () => { try { return localStorage.getItem(KEY) || "en"; } catch (e) { return "en"; } };

  function apply(lang) {
    const html = document.documentElement;
    html.lang = lang; html.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll(SEL).forEach(el => {
      el.childNodes.forEach(n => {
        if (n.nodeType !== 3) return;
        if (n._en === undefined) n._en = n.nodeValue;
        const raw = n._en, key = raw.trim();
        if (lang === "en" || !key) { n.nodeValue = raw; return; }
        const t = T[key] || T[key.replace(/\s+/g, " ")];
        n.nodeValue = t ? raw.replace(key, t[IDX[lang]]) : raw;
      });
    });
  }

  function mount() {
    const bar = document.querySelector(".utility .wrap");
    if (bar && !document.getElementById("lang-select")) {
      const sel = document.createElement("select");
      sel.id = "lang-select"; sel.className = "lang-select"; sel.setAttribute("aria-label", "Language");
      sel.innerHTML = Object.entries(LANGS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
      sel.value = get();
      sel.addEventListener("change", () => { try { localStorage.setItem(KEY, sel.value); } catch (e) {} apply(sel.value); });
      bar.appendChild(sel);
    }
    if (get() !== "en") apply(get());
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
  // content added later (live news tabs, report builder) is translated when it appears
  let pending = false;
  new MutationObserver(() => {
    if (pending || get() === "en") return;
    pending = true;
    requestAnimationFrame(() => { pending = false; apply(get()); });
  }).observe(document.body || document.documentElement, { childList: true, subtree: true });
})();
