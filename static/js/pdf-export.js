/**
 * PDF-экспорт (Р8) — клиентский экспорт таблиц в PDF через html2canvas + jspdf.
 * Подключает библиотеки лениво (CDN) при первом вызове.
 */
(function() {
    var jspdfLoaded = false;
    var h2cLoaded = false;

    function loadScript(src, cb) {
        var s = document.createElement('script');
        s.src = src;
        s.onload = cb;
        s.onerror = function() { showToast('Ошибка загрузки библиотеки PDF', 'error'); };
        document.head.appendChild(s);
    }

    function ensureLibs(cb) {
        var pending = 0;
        if (!window.html2canvas) {
            pending++;
            loadScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js', function() {
                h2cLoaded = true;
                if (--pending === 0) cb();
            });
        }
        if (!window.jspdf || !window.jspdf.jsPDF) {
            pending++;
            loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js', function() {
                jspdfLoaded = true;
                if (--pending === 0) cb();
            });
        }
        if (pending === 0) cb();
    }

    /**
     * Экспортирует DOM-элемент (обычно таблицу) в PDF.
     * @param {Object} opts
     * @param {string|HTMLElement} opts.element — селектор или элемент для экспорта
     * @param {string} [opts.filename='export.pdf'] — имя файла
     * @param {string} [opts.title] — заголовок в PDF
     * @param {string} [opts.orientation='landscape'] — 'portrait' или 'landscape'
     */
    window.exportToPdf = function(opts) {
        opts = opts || {};
        var el = typeof opts.element === 'string' ? document.querySelector(opts.element) : opts.element;
        if (!el) { showToast('Элемент для экспорта не найден', 'error'); return; }

        showToast('Подготовка PDF...', 'warning');

        ensureLibs(function() {
            var jsPDF = window.jspdf.jsPDF;

            html2canvas(el, {
                scale: 1.5,
                useCORS: true,
                logging: false,
                backgroundColor: '#ffffff'
            }).then(function(canvas) {
                var orientation = opts.orientation || 'landscape';
                var pdf = new jsPDF(orientation, 'mm', 'a4');
                var pageWidth = pdf.internal.pageSize.getWidth();
                var pageHeight = pdf.internal.pageSize.getHeight();
                var margin = 10;

                // Title
                if (opts.title) {
                    pdf.setFontSize(14);
                    pdf.text(opts.title, margin, margin + 5);
                    margin += 12;
                }

                // Date
                pdf.setFontSize(9);
                pdf.setTextColor(128);
                pdf.text('Дата: ' + new Date().toLocaleDateString('ru-RU'), pageWidth - 50, 8);
                pdf.setTextColor(0);

                var imgWidth = pageWidth - 20;
                var imgHeight = (canvas.height * imgWidth) / canvas.width;
                var imgData = canvas.toDataURL('image/jpeg', 0.85);

                // Multi-page if needed
                var y = margin;
                var availHeight = pageHeight - margin - 10;

                if (imgHeight <= availHeight) {
                    pdf.addImage(imgData, 'JPEG', 10, y, imgWidth, imgHeight);
                } else {
                    // Split across pages
                    var remainingHeight = imgHeight;
                    var srcY = 0;
                    while (remainingHeight > 0) {
                        var sliceHeight = Math.min(availHeight, remainingHeight);
                        // Create canvas slice
                        var sliceCanvas = document.createElement('canvas');
                        sliceCanvas.width = canvas.width;
                        sliceCanvas.height = (sliceHeight / imgHeight) * canvas.height;
                        var ctx = sliceCanvas.getContext('2d');
                        ctx.drawImage(canvas, 0, srcY, canvas.width, sliceCanvas.height, 0, 0, sliceCanvas.width, sliceCanvas.height);

                        pdf.addImage(sliceCanvas.toDataURL('image/jpeg', 0.85), 'JPEG', 10, y, imgWidth, sliceHeight);
                        remainingHeight -= sliceHeight;
                        srcY += sliceCanvas.height;

                        if (remainingHeight > 0) {
                            pdf.addPage();
                            y = 10;
                            availHeight = pageHeight - 20;
                        }
                    }
                }

                pdf.save(opts.filename || 'export.pdf');
                showToast('PDF сохранён', 'success');
            }).catch(function(err) {
                console.error('PDF export error:', err);
                showToast('Ошибка генерации PDF', 'error');
            });
        });
    };
})();
