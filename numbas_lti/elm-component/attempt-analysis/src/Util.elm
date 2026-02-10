module Util exposing 
    (alpha
    , indexedConcatMap
    )

import Tuple exposing (pair)

alpha : Int -> String
alpha n =
  let
    alphabet = "abcdefghijklmnopqrstuvwxyz"
  in
    String.slice n (n+1) alphabet

indexedConcatMap : (Int -> a -> List b) -> List a -> List b
indexedConcatMap fn = List.indexedMap pair >> List.concatMap (\(a,b) -> fn a b)
