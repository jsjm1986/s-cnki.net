const { createApp, ref, reactive } = Vue;

const app = createApp({
    setup() {
        const searchQuery = ref('');
        const articles = ref([]);
        const loading = ref(false);
        const hasSearched = ref(false);
        const currentPage = ref(1);
        const totalPages = ref(0);
        const totalItems = ref(0);
        const showFilters = ref(false);
        const showSettings = ref(false);
        
        const filters = reactive({
            year: '',
            type: ''
        });
        
        const analysisDialog = reactive({
            visible: false,
            loading: false
        });
        
        const analysis = ref(null);
        
        const years = Array.from(
            { length: new Date().getFullYear() - 1989 },
            (_, i) => String(new Date().getFullYear() - i)
        );
        
        const searchSettings = reactive({
            maxPapers: 100,
            minCitations: 0,
            sortBy: 'relevance'
        });

        // 搜索文献
        async function searchArticles() {
            if (!searchQuery.value.trim()) return;
            
            loading.value = true;
            hasSearched.value = true;
            
            try {
                const response = await fetch('http://localhost:8000/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: searchQuery.value,
                        page: currentPage.value,
                        filters: filters,
                        settings: {
                            max_papers: searchSettings.maxPapers,
                            min_citations: searchSettings.minCitations,
                            sort_by: searchSettings.sortBy
                        }
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    articles.value = data.data.articles;
                    totalPages.value = data.data.total_pages;
                    totalItems.value = data.data.total_count;
                    
                    // 根据排序设置处理文章列表
                    if (searchSettings.sortBy === 'citations') {
                        articles.value.sort((a, b) => b.citations - a.citations);
                    } else if (searchSettings.sortBy === 'date') {
                        articles.value.sort((a, b) => new Date(b.date) - new Date(a.date));
                    }
                } else {
                    ElMessage.error(data.detail || '搜索失败');
                }
            } catch (error) {
                console.error('搜索出错：', error);
                ElMessage.error('搜索服务出现错误，请稍后重试');
            } finally {
                loading.value = false;
            }
        }

        // 分析文献
        async function analyzePaper(article) {
            analysisDialog.visible = true;
            analysisDialog.loading = true;
            analysis.value = null;
            
            try {
                const response = await fetch(`http://localhost:8000/summarize/${article.id}`);
                const data = await response.json();
                
                if (data.status === 'success') {
                    analysis.value = data.data;
                } else {
                    ElMessage.error(data.detail || '分析失败');
                }
            } catch (error) {
                console.error('分析出错：', error);
                ElMessage.error('分析服务出现错误，请稍后重试');
            } finally {
                analysisDialog.loading = false;
            }
        }

        // 格式化分析结果
        function formatAnalysis(text) {
            if (!text) return '';
            return marked.parse(text);
        }

        // 处理分页
        async function handlePageChange(page) {
            currentPage.value = page;
            await searchArticles();
        }

        // 下载PDF
        function downloadPDF(article) {
            ElMessage.info('PDF下载功能正在开发中');
        }

        // 显示文章详情
        function showArticleDetail(article) {
            // 实现文章详情查看功能
        }

        return {
            searchQuery,
            articles,
            loading,
            hasSearched,
            currentPage,
            totalPages,
            totalItems,
            showFilters,
            filters,
            years,
            analysisDialog,
            analysis,
            searchArticles,
            analyzePaper,
            formatAnalysis,
            handlePageChange,
            downloadPDF,
            showArticleDetail
        };
    }
});

app.use(ElementPlus);
app.mount('#app'); 