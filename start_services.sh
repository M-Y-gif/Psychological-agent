#!/bin/bash
# ============================================
# 心理Agent 一键启动脚本
# ============================================
# 用法：
#   ./start_services.sh          # 启动所有服务
#   ./start_services.sh bert     # 只启动BERT微服务
#   ./start_services.sh multi    # 只启动多模态微服务
#   ./start_services.sh stop     # 停止所有服务
# ============================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Users/yuansunming/miniconda3/envs/yolov5/bin/python3"
BERT_PORT=8091
MULTI_PORT=8090

cd "$PROJECT_DIR"

stop_all() {
    echo "🛑 停止所有服务..."
    pkill -f "risk_classifier.py" 2>/dev/null && echo "   BERT微服务已停止" || echo "   BERT微服务未运行"
    pkill -f "multimodal/app.py" 2>/dev/null && echo "   多模态微服务已停止" || echo "   多模态微服务未运行"
    pkill -f "chroma run" 2>/dev/null && echo "   Chroma已停止" || echo "   Chroma未运行"
    echo "✅ 完成"
}

start_bert() {
    if lsof -i :$BERT_PORT >/dev/null 2>&1; then
        echo "⚠️  BERT微服务已在运行（端口 $BERT_PORT）"
        return
    fi
    echo "🧠 启动BERT风险分类微服务（端口 $BERT_PORT）..."
    nohup $PYTHON multimodal/risk_classifier.py > /tmp/bert_server.log 2>&1 &
    echo "   PID: $!"
    echo "   等待模型加载（约20-30秒）..."
    for i in $(seq 1 30); do
        if curl -s http://localhost:$BERT_PORT/api/health >/dev/null 2>&1; then
            echo "   ✅ BERT微服务已就绪！"
            curl -s http://localhost:$BERT_PORT/api/health | python3 -m json.tool
            return
        fi
        sleep 1
    done
    echo "   ⚠️  超时，查看日志：cat /tmp/bert_server.log"
}

start_multi() {
    if lsof -i :$MULTI_PORT >/dev/null 2>&1; then
        echo "⚠️  多模态微服务已在运行（端口 $MULTI_PORT）"
        return
    fi
    echo "🎭 启动多模态微服务（端口 $MULTI_PORT，CNN表情引擎）..."
    EMOTION_ENGINE=cnn nohup $PYTHON multimodal/app.py > /tmp/multi_server.log 2>&1 &
    echo "   PID: $!"
    echo "   等待模型加载..."
    sleep 10
    if curl -s http://localhost:$MULTI_PORT/docs >/dev/null 2>&1; then
        echo "   ✅ 多模态微服务已就绪！"
    else
        echo "   ⚠️  可能还在加载Whisper模型，查看日志：cat /tmp/multi_server.log"
    fi
}

case "${1:-all}" in
    stop)
        stop_all
        ;;
    bert)
        start_bert
        ;;
    multi)
        start_multi
        ;;
    chroma)
        if lsof -i :8000 >/dev/null 2>&1; then
            echo "⚠️  Chroma 已在运行（端口 8000）"
        else
            echo "📦 启动 Chroma 向量数据库（端口 8000）..."
            nohup chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data > /tmp/chroma_server.log 2>&1 &
            echo "   PID: $!"
            sleep 3
            if lsof -i :8000 >/dev/null 2>&1; then
                echo "   ✅ Chroma 已就绪！"
            else
                echo "   ⚠️  启动失败，查看日志：cat /tmp/chroma_server.log"
                echo "   提示：需要先 pip install chromadb"
            fi
        fi
        ;;
    all)
        echo "=========================================="
        echo "  心理Agent 服务启动"
        echo "=========================================="
        # Chroma
        if ! lsof -i :8000 >/dev/null 2>&1; then
            echo "📦 启动 Chroma 向量数据库（端口 8000）..."
            nohup chroma run --host 0.0.0.0 --port 8000 --path ./chroma-data > /tmp/chroma_server.log 2>&1 &
            sleep 3
            if lsof -i :8000 >/dev/null 2>&1; then
                echo "   ✅ Chroma 已就绪"
            else
                echo "   ⚠️  Chroma 启动失败，Java 后端将无法启动"
                echo "   请先执行: pip install chromadb"
            fi
        else
            echo "✅ Chroma 已在运行"
        fi
        echo ""
        start_bert
        echo ""
        start_multi
        echo ""
        echo "=========================================="
        echo "  服务状态："
        echo "  Chroma 向量库:   http://localhost:8000"
        echo "  BERT 风险分类:   http://localhost:$BERT_PORT"
        echo "  多模态感知:      http://localhost:$MULTI_PORT"
        echo "  Java 后端:       请执行 ./run.sh 或在 IDEA 中运行"
        echo "=========================================="
        echo ""
        echo "  停止所有服务:  ./start_services.sh stop"
        echo "  查看日志:"
        echo "    Chroma:   cat /tmp/chroma_server.log"
        echo "    BERT:     cat /tmp/bert_server.log"
        echo "    多模态:   cat /tmp/multi_server.log"
        echo ""
        echo "  测试 BERT:"
        echo "    curl -X POST http://localhost:$BERT_PORT/api/risk_classify \\"
        echo "      -H 'Content-Type: application/json' -d '{\"text\":\"活着没意思\"}'"
        ;;
    *)
        echo "用法: $0 {all|bert|multi|stop}"
        ;;
esac
