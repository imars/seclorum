// webpack.config.mjs
import CopyWebpackPlugin from 'copy-webpack-plugin';
import HtmlWebpackPlugin from 'html-webpack-plugin';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  mode: 'development',
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.(js|mjs)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env'],
          },
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.(jpg|jpeg|png)$/,
        type: 'asset/resource',
        generator: {
          filename: 'assets/skybox/[name][ext]', // Match settings.js paths
        },
      },
      {
        test: /\.(?:js|mjs|cjs)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [['@babel/preset-env', { targets: 'defaults' }]],
          },
        },
      },
      {
        test: /worker\.js$/,
        use: {
          loader: 'worker-loader',
          options: {
            filename: '[name].js',
          },
        },
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: path.resolve(__dirname, 'public/index.html'),
      filename: 'index.html',
    }),
    new CopyWebpackPlugin({
      patterns: [
        {
          from: path.resolve(__dirname, 'public/assets/skybox'),
          to: path.resolve(__dirname, 'dist/assets/skybox'),
          noErrorOnMissing: true,
          globOptions: {
            ignore: ['**/.DS_Store'],
          },
        },
      ],
    }),
  ],
  devServer: {
    static: {
      directory: path.join(__dirname, 'dist'),
      publicPath: '/',
    },
    compress: true,
    port: 8080,
    hot: true,
    open: true,
    historyApiFallback: {
      index: '/index.html',
    },
    headers: {
      'Cache-Control': 'no-store',
    },
  },
  resolve: {
    extensions: ['.js', '.mjs'],
  },
};
