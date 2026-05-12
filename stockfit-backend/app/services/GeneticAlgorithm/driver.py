from data_pre_processing import data
from hyper_parameter_tuning import tune_hyperparameters, final_evaluation

tuning_results= tune_hyperparameters(data)
tunning_results={
    "best_params": {'cxpb': np.float64(0.9), 'mutpb': np.float64(0.9), 'indpb': np.float64(0.15), 'master_alpha': np.float64(0.7)},
    "all_results": pd.DataFrame()
    }

y= final_evaluation (data,tuning_results)