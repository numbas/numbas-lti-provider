module PartPath exposing 
  ( PartPath
  , fromString
  , toString
  , label
  , parse_path
  )

import Parser as P exposing (Parser, (|.), (|=))
import Util exposing (alpha)

type alias PartPath = (Int, Int, Maybe Int)

fi = String.fromInt

parse_path : Parser PartPath
parse_path =
  P.succeed (\q p g -> (q,p,g))
  |. P.symbol "q"
  |= P.int
  |. P.symbol "p"
  |= P.int
  |= P.oneOf
    [ P.succeed Just 
      |. P.symbol "g"
      |= P.int
    , P.succeed Nothing
    ]

fromString : String -> Maybe PartPath
fromString = P.run parse_path >> Result.toMaybe

toString : PartPath -> String
toString (qn,pn,mgn) =
  let
    prefix = "q"++(fi qn)++"p"++(fi pn)
    gap = case mgn of
      Nothing -> ""
      Just gn -> "g"++(fi gn)
  in
    prefix++gap

label : PartPath -> String
label (qn,pn,mgn) = case mgn of
  Just gn -> "gap "++(fi gn)
  Nothing -> (alpha pn)++")"
