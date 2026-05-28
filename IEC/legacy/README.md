# Legacy 2-Candidate IEC System

このディレクトリには、古い2候補ペア比較IECシステムのファイルが保存されています。

## 内容

- `gen/` - 最後に生成された2候補ペア（A/B.obj）
- `gen_log/` - 世代履歴（gen0-gen4）
- `elite/` - お気に入り形態アーカイブ
- `test_gnn_gen/` - テストデータ
- `model/` - LogisticRegressionモデル（preference_model.pkl, scaler.pkl）
- `tools/` - 旧訓練スクリプト（train_preference_model.py）

## 新システムへの移行

現在は **6候補生成システム** (Phase 1-3) への移行を推奨しています。

新システムの使用方法:
```bash
cd ../tools
python generate_generation.py --gen-id 0
python compare_generation.py --gen-id 0
```

詳細は親ディレクトリの `README.md` と `WORKFLOW.md` を参照してください。

## 参考

このフォルダのファイルは参照用として保存されています。必要に応じて参照できますが、新規開発には新システムの使用を推奨します。
