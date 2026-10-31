"""Train leakage-safe baselines on the original synthetic dataset.
Run from repository root: python ml/train.py
Do not interpret evaluation on synthetic records as real-world performance.
"""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, roc_auc_score, confusion_matrix, accuracy_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'original_synthetic_fraud.csv'
OUT=ROOT/'backend'/'models';OUT.mkdir(parents=True,exist_ok=True)
df=pd.read_csv(DATA)
assert set(df['Label'].unique())=={0,1}
X=df.drop(columns=['Label']); y=df['Label']
# Synthetic dataset has no timestamps or account IDs; stratified random split is a limitation.
X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
cat=list(X.select_dtypes(include='object').columns)
num=[x for x in X.columns if x not in cat]
pre=ColumnTransformer([('numeric',SimpleImputer(strategy='median'),num),('categorical',make_pipeline(SimpleImputer(strategy='most_frequent'),OneHotEncoder(handle_unknown='ignore',sparse_output=False)),cat)])
model=Pipeline([('preprocessor',pre),('classifier',RandomForestClassifier(n_estimators=120,min_samples_leaf=3,max_depth=16,random_state=42,n_jobs=-1,class_weight='balanced'))])
model.fit(X_train,y_train)
p=model.predict_proba(X_test)[:,1]
# A fixed threshold is a demonstration setting, not an operational fraud policy.
pred=(p>=.5).astype(int)
cm=confusion_matrix(y_test,pred)
metrics={'dataset':'Original user-provided synthetic dataset','rows':len(df),'fraud_rate':float(y.mean()),'train_rows':len(X_train),'test_rows':len(X_test),'split':'Stratified random 80/20; no account IDs or timestamps available','accuracy':float(accuracy_score(y_test,pred)),'precision':float(precision_score(y_test,pred,zero_division=0)),'recall':float(recall_score(y_test,pred,zero_division=0)),'f1':float(f1_score(y_test,pred,zero_division=0)),'pr_auc':float(average_precision_score(y_test,p)),'roc_auc':float(roc_auc_score(y_test,p)),'confusion_matrix':cm.tolist(),'threshold':0.5,'model':'RandomForestClassifier','note':'Synthetic-data evaluation only; not validated for real UPI transactions. Sandbox form does not supply all 20 features.'}
joblib.dump({'pipeline':model,'columns':list(X.columns),'categories':{c:sorted(X[c].dropna().unique().tolist()) for c in cat},'medians':X_train[num].median().to_dict()},OUT/'fraud_pipeline.joblib')
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2))
print(json.dumps(metrics,indent=2))
